import numpy as np
from PIL import Image

from printer_server.printer_control.print_control import *


def um_to_px(um):
    """Return the number of pixels corresponding to the length 'um' by
    rounding 'um' to the nearest 'pixel_pitch' increment.
    """
    pixel_pitch = 7.6
    return int(round(um / pixel_pitch))


def shift_image(img, x=0, y=0):
    """Shift the image by the specified number of pixels in x and y.
    Pixels that get shifted out of the image on one side disappear and
    the new pixels on the opposite side are copied from the original
    edge. This is accomplished by converting the image to a numpy array
    and building a list of row and column indicies to slice it with.
    """
    new_filename = img.parent / f"{img.stem}_shifted_{x}x_{y}y.png"
    img = np.array(Image.open(img))
    idx = [[], []]
    for axis, shift_by in enumerate((y, -x)):
        if shift_by > 0:
            idx[axis] = list(range(shift_by, img.shape[axis]))
            for _ in range(shift_by):
                idx[axis].append(img.shape[axis] - 1)
        elif shift_by < 0:
            idx[axis] = list(range(0, img.shape[axis] + shift_by))
            for _ in range(-shift_by):
                idx[axis].insert(0, 0)
    if idx[0]:
        img = img[idx[0], :]
    if idx[1]:
        img = img[:, idx[1]]
    img = Image.fromarray(img).convert("L")
    log.info("Saving new defocused image %s", new_filename)
    img.save(new_filename)
    return Path(new_filename)


class KDCControl(PrintControl):
    def __init__(self):
        """Create KDC handle"""
        super().__init__()
        self.kdc = driver_handles.kdc
        self.kdc_thread = None
        self.defocus_um = None

    def get_focus(self):
        """Return KDC position"""
        return self.kdc.getCurrentPos()

    def change_focus(self, pos):
        """Move KDC stage to position"""
        self.write_to_event_log("Start Distance Movement")
        self.kdc.move(pos, relative=False)
        self.write_to_event_log("Finish Distance Movement")

    def kdc_setup_thread(self):
        """Initialize and home ThorLabs stage"""
        if not self.kdc.homed:
            self.kdc.home()
            self.focused_position = get_last_focused_position_from_logs()
            self.kdc.move(self.focused_position, relative=False)

    def connect_hardware(self):
        self.kdc.connect()
        super().connect_hardware()
        if self.kdc.port is None:
            log.error("KDC101 failed to connect!")
            self.all_hardware_connected = False
        
    def initalize_hardware(self):
        self.kdc_thread = Thread(log, name="kdc_control_setup_thread", target=self.kdc_setup_thread, args=[])
        self.kdc_thread.start()
        super().initalize_hardware()
        self.kdc_thread.join()

    def pre_exposure_tasks(self, settings, light_engine):
        """If layer is defocused, move KDC and shift image"""
        self.defocus_um = settings["Relative focus position (um)"]
        if self.defocus_um != 0:
            self.kdc_thread = Thread(
                log, 
                name="kdc_control_change_focus_thread",
                target=self.change_focus,
                args=[self.focused_position + self.defocus_um],
            )
            self.kdc_thread.start()
            self.image = shift_image(self.image, x=um_to_px(self.defocus_um))
        return super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, settings, light_engine):
        """If layer is defocused, wait for KDC thread to finish"""
        if self.defocus_um != 0:
            self.kdc_thread.join()
        return super().pre_exposure_joins(settings, light_engine)

    def post_exposure_tasks(self, msg):
        """If layer is defocused, return KDC to focus position"""
        # fix focus if this exposure was defocused
        if self.defocus_um != 0:
            self.change_focus(self.focused_position)
        super().post_exposure_tasks(msg)
