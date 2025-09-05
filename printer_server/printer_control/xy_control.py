import logging

from printer_server.threading_wrapper import Thread
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles
from printer_server.printer_control.print_control import PrintControl, PrintingException, run_in_thread
from printer_server.views.calibration import (
    get_last_calibration_positions_from_logs,
)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class XYControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.xy_stage = driver_handles.xy_stage

    def create_logs(self):
        super().create_logs()
        self.xy_stage.setup_log_file(str(self.current_job / "logs"))

    def connect_hardware(self):
        self.xy_thread = Thread(log, name="xy_control_connect_thread", target=self.xy_stage.connect)
        self.xy_thread.start()
        super().connect_hardware()
        self.xy_thread.join()
        if not self.xy_stage.connected or self.xy_thread.exception is not None:
            log.error("XY stage failed to connect!")
            self.failed_hardware["XY Stage"] = self.xy_stage

    def initialize_hardware(self):
        if driver_handles.focus_stage.config_dict.get("link_focus_and_y_movement", False):
            self.xy_stage.linked_focus_stage = driver_handles.focus_stage
        x_pos = self.coord_systems["parked"]["X"]
        y_pos = self.coord_systems["parked"]["Y"]
        self.xy_thread = Thread(log, name="xy_control_init_thread", target=self.xy_stage.initialize_and_positionXY, args=[x_pos, y_pos])
        self.xy_thread.start()
        super().initialize_hardware()
        self.xy_thread.join()
        if self.xy_thread.exception is not None:
            log.error("XY stage failed to initialize!")
            self.failed_hardware["XY Stage"] = self.xy_stage
            return
        self.xy_stage.initialized = True

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self):
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            try:
                self.xy_stage.logging_start()
            except Exception as ex:
                log.critical("Unable to communicate with xy stage (%s)", ex, exc_info=True)
                self.failed_hardware["XY Stage"] = self.xy_stage
                raise PrintingException()
            super().planarization_step_1()

    @run_in_thread("initialized", "Cancel Planarization")
    def cancel_planarization(self):
            try:
                self.xy_stage.logging_stop()
            except Exception as ex:
                log.critical("Unable to communicate with xy stage (%s)", ex, exc_info=True)
                self.failed_hardware["XY Stage"] = self.xy_stage
                raise PrintingException()
            super().cancel_planarization()

    def pre_exposure_tasks(self, settings, light_engine):
        """Move X, Y, and Focus stages to exposure positions"""
        defaults_layer_settings = self.print_settings.get("Default layer settings")
        default_image_settings = defaults_layer_settings.get("Image settings")
        self.default_x_offset = default_image_settings.get("Image x offset (um)", 0)
        self.default_y_offset = default_image_settings.get("Image y offset (um)", 0)

        x_offset = float(settings.get("Image x offset (um)", self.default_x_offset))
        y_offset = float(settings.get("Image y offset (um)", self.default_y_offset))
        screen_light_engine = self.convert_le_to_screen_le(light_engine)

        if screen_light_engine == "wintech":
            calibration_positions = get_last_calibration_positions_from_logs()
            x_adj = calibration_positions.get("x_drift",0.0) + calibration_positions.get("xy_shift",0.0)*y_offset/1000 + calibration_positions.get("xx_shift",0.0)*x_offset/1000
            y_adj = calibration_positions.get("y_drift",0.0) + calibration_positions.get("yx_shift",0.0)*x_offset/1000 + calibration_positions.get("yy_shift",0.0)*y_offset/1000
            x_pos = x_offset/1000 + self.coord_systems[screen_light_engine]["X"] + x_adj/1000
            y_pos =  y_offset/1000 + self.coord_systems[screen_light_engine]["Y"] + y_adj/1000
        else:
            x_pos = x_offset/1000 + self.coord_systems[screen_light_engine]["X"]
            y_pos =  y_offset/1000 + self.coord_systems[screen_light_engine]["Y"]
        self.xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False)

        super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, light_engine):
        """Join X, Y, and Focus threads"""
        for thread in self.xy_threads:
            if thread is not None:
                thread.join()
                if thread.exception is not None:
                    log.critical("Unable to move xy stage")
                    self.failed_hardware["XY Stage"] = self.xy_stage
                    raise PrintingException()
        return super().pre_exposure_joins(light_engine)

    def post_print_tasks(self):
        super().post_print_tasks()
        # set paused position
        x_pos = self.coord_systems["parked"]["X"]
        y_pos = self.coord_systems["parked"]["Y"]
        self.xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False, speed_x=None, speed_y=None, acceleration_x=None, acceleration_y=None)
                
    def post_print_joins(self):
        for thread in self.xy_threads:
            if thread is not None:
                thread.join()
                if thread.exception is not None:
                    log.critical("Unable to move xy stage")
                    self.failed_hardware["XY Stage"] = self.xy_stage
                    raise PrintingException()
        return super().post_print_joins()

    def finish_print(self):
        try:
            self.xy_stage.logging_stop()
            self.xy_stage.setup_log_file(None)
        except Exception as ex:
            log.critical("Unable to communicate with xy stage (%s)", ex, exc_info=True)
            self.failed_hardware["XY Stage"] = self.xy_stage
            raise PrintingException()
        super().finish_print()