import time
import logging
import numpy as np
from PIL import Image
from pathlib import Path

from printer_server.threading_wrapper import Thread
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles
from printer_server.printer_control.print_control import PrintControl, PrintingException, run_in_thread
from printer_server.views.calibration import (
    get_last_calibration_positions_from_logs,
)

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
        self.focus_stage.setup_log_file(str(self.current_job / "logs"))

    def connect_hardware(self):
        self.focus_thread = Thread(log, name="focus_control_connect_thread", target=self.focus_stage.connect)
        self.focus_thread.start()
        super().connect_hardware()
        self.focus_thread.join()
        if not self.focus_stage.connected or self.focus_thread.exception is not None:
            log.error("Focus stage failed to connect!")
            self.failed_hardware["Focus Stage"] = self.focus_stage

    def initialize_hardware(self):
        if self.coord_systems is not None:
            self.focus = self.coord_systems["parked"]["Focus"]
        else:
            self.focus = get_last_calibration_positions_from_logs().get("focus",0) / 1000
        self.focus_thread = Thread(log, name="focus_control_init_thread", target=self.focus_stage.initialize_and_positionFocus, args=[self.focus])
        self.focus_thread.start()
        super().initialize_hardware()
        self.focus_thread.join()
        if self.focus_thread.exception is not None:
            log.error("Focus stage failed to initialize!")
            self.failed_hardware["Focus Stage"] = self.focus_stage

    def get_focus(self):
        """Return 'Focus' axis position in um"""
        try:
            return self.focus_stage.getFocusPosition() * 1000
        except Exception as ex:
            log.critical("Unable to communicate with focus stage (%s)", ex, exc_info=True)
            self.failed_hardware["Focus Stage"] = self.focus_stage
            raise PrintingException()

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self):
        """Lower the build platform for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            try:
                self.focus_stage.logging_start()
            except Exception as ex:
                log.critical("Unable to communicate with focus stage (%s)", ex, exc_info=True)
                self.failed_hardware["Focus Stage"] = self.focus_stage
                raise PrintingException()
            super().planarization_step_1()


    @run_in_thread("initialized", "Cancel Planarization")
    def cancel_planarization(self):
            try:
                self.focus_stage.logging_stop()
            except Exception as ex:
                log.critical("Unable to communicate with focus stage (%s)", ex, exc_info=True)
                self.failed_hardware["Focus Stage"] = self.focus_stage
                raise PrintingException()
            super().cancel_planarization()

    def get_exposure_defocus(self, settings, light_engine):
        self.focus = get_last_calibration_positions_from_logs().get(f"focus",0)/1000
        self.defocus_um = settings["Relative focus position (um)"]

    def pre_exposure_tasks(self, settings, light_engine):
        self.get_exposure_defocus(settings, light_engine)

        need_to_shift_image = self.focus_stage.config_dict.get("moving_shifts_image", False)
        if need_to_shift_image:
            shift = um_to_px(self.defocus_um)
            if settings.get("Mirror image long axis", False):
                shift = -shift
            self.image = shift_image(self.image, x=shift)
        
        if "coord_systems" in config_dict.keys():
            # fetch x/y offsets to pass to coordinate system transformation function
            defaults_layer_settings = self.print_settings.get("Default layer settings")
            default_image_settings = defaults_layer_settings.get("Image settings")
            self.default_raw_x_offset = default_image_settings.get("Image x offset (um)", 0)
            self.default_raw_y_offset = default_image_settings.get("Image y offset (um)", 0)

            x_offset = float(settings.get("Image x offset (um)", self.default_raw_x_offset))
            y_offset = float(settings.get("Image y offset (um)", self.default_raw_y_offset))

            le = self.convert_json_le_to_le(light_engine)
            self.focus_thread = self.move_xyf_stages_in_coordinate_system(
                coord_system_name=le,
                x=x_offset/1000,
                y=y_offset/1000,
                f=self.focus + self.defocus_um/1000,
                light_engine=le,
                move_xy=False,
                join=False
            )
        else:
            self.focus_thread = [self.focus_stage.threadedFocusMove(log, self.focus + self.defocus_um/1000, join=False)]
        time.sleep(0.1)
        return super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, light_engine):
        """Join Focus threads"""
        # check if focus_thread is list (if coordinate system movement was used) or single thread (if not)
        for thread in self.focus_thread:
            if thread is not None:
                thread.join()
                if thread.exception is not None:
                    log.critical("Unable to move focus stage")
                    self.failed_hardware["Focus Stage"] = self.focus_stage
                    raise PrintingException()
        return super().pre_exposure_joins(light_engine)

    def post_print_tasks(self):
        super().post_print_tasks()
        self.focus_thread = self.focus_stage.threadedFocusMove(log, self.focus, join=False)
            
    def post_print_joins(self):
        if self.focus_thread is not None:
            self.focus_thread.join()
            if self.focus_thread.exception is not None:
                log.critical("Unable to move focus stage")
                self.failed_hardware["Focus Stage"] = self.focus_stage
                raise PrintingException()
        return super().post_print_joins()

    def finish_print(self):
        try:
            self.focus_stage.logging_stop()
            self.focus_stage.setup_log_file(None)
        except Exception as ex:
            log.critical("Unable to communicate with focus stage (%s)", ex, exc_info=True)
            self.failed_hardware["Focus Stage"] = self.focus_stage
            raise PrintingException()
        super().finish_print()