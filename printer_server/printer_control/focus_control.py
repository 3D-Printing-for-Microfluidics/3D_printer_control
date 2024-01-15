import numpy as np
from PIL import Image

from printer_server.printer_control.print_control import *

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

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

class FocusControl(PrintControl):
     def __init__(self):
        super().__init__()
        self.focus_stage = driver_handles.focus_stage
        self.defocus_um = None

    def create_logs(self):
        super().create_logs()
        self.focus_stage.setup_log_file(str(self.current_job))

    def get_focus(self):
        """Return 'Focus' axis position in um"""
        return int(
            self.focus_stage.getFocusPosition() * 1000
        )

    def connect_hardware(self):
        focus_thread = Thread(log, name="focus_control_setup_thread", target=self.focus_stage.connect, args=[self.shutdown])
        focus_thread.start()
        super().connect_hardware()
        focus_thread.join()
        if not self.focus_stage.connected:
            self.all_hardware_connected = False

    def initalize_hardware(self):
        if self.coord_systems is not None:
            self.focused_position = self.coord_systems["visitech"]["Focus"]
        else:
            self.focused_position = get_last_calibration_positions_from_logs()["distance"]
        focus_thread = self.focus_stage.initialize_and_positionFocus(focus_pos, join=False)
        super().initalize_hardware()
        if focus_thread is not None:
            focus_thread.join()
        self.focus_stage.initialized = True

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self, run_in_thread=True):
        """Lower the build platform for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            super().planarization_step_1(run_in_thread=False)
            self.focus_stage.logging_start()

    def post_print_tasks(self):
        super().post_print_tasks()
        self.focus_stage.threadedFocusMove(log, self.focused_position, join=False)
        if focus_thread is not None:
            focus_thread.join()

    def get_exposure_defocus(self, settings, light_engine):
        self.defocus_um = settings["Relative focus position (um)"]

    def pre_exposure_tasks(self, settings, light_engine):
        self.get_exposure_defocus_position(settings, light_engine)
        if self.defocus_um != 0:
            self.focus_thread = self.focus_stage.threadedFocusMove(log, self.focused_position + self.defocus_um, join=False)
            self.focus_thread.start()
        return super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, light_engine):
        """Join Focus threads"""
        if self.defocus_um != 0:
            if self.focus_thread is not None:
                self.focus_thread.join()
        return super().pre_exposure_joins(light_engine)

    def post_exposure_tasks(self, msg):
        """If layer is defocused, return KDC to focus position"""
        # fix focus if this exposure was defocused
        if self.defocus_um != 0:
            self.focus_stage.threadedFocusMove(log, self.focused_position, join=True)
        super().post_exposure_tasks(msg)

    def finish_print(self):
        self.focus_stage.logging_stop()
        self.focus_stage.setup_log_file(None)
        super().finish_print()