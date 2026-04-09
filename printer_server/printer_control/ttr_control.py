import logging
import time

from printer_server.threading_wrapper import Thread
from printer_server.hardware_configuration.hardware_configuration import driver_handles
from printer_server.printer_control.print_control import PrintControl, PrintingException, run_in_thread
from printer_server.views.calibration import (
    get_last_calibration_positions_from_logs,
)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class TTRControl(PrintControl):
    def __init__(self):
        super().__init__()

        # hardware handles
        self.ttr_stage = driver_handles.ttr_stage
        self.ttr_threads = None

    def create_logs(self):
        super().create_logs()
        self.ttr_stage.setup_log_file(str(self.current_job / "logs"))

    def connect_hardware(self):
        self.ttr_thread = Thread(log, name="ttr_control_connect_thread", target=self.ttr_stage.connect)
        self.ttr_thread.start()
        super().connect_hardware()
        self.ttr_thread.join()
        if not self.ttr_stage.connected or self.ttr_thread.exception is not None:
            log.error("TTR stage failed to connect!")
            self.failed_hardware["TTR stage"] = self.ttr_stage

    def initialize_hardware(self):
        self.tip = None
        self.tilt = None
        last_positions = get_last_calibration_positions_from_logs()

        matching_keys = [key for key in last_positions if "_tip_base" in str(key) or "_tilt_base" in str(key)]
        if len(matching_keys) > 0:
            self.tip = last_positions.get(matching_keys[0].replace("tilt", "tip"),None)
            self.tilt = last_positions.get(matching_keys[0].replace("tip", "tilt"),None)
        if self.tip is None:
            self.tip = last_positions.get("tip",None)
        if self.tilt is None:
            self.tilt = last_positions.get("tilt",None)
        self.rotate = last_positions.get(f"rotate",None)

        if self.tip is not None:
            self.tip /= 1000
        if self.tilt is not None:
            self.tilt /= 1000
        if self.rotate is not None:
            self.rotate /= 1000
        self.ttr_thread = Thread(log, name="ttr_control_init_thread", target=self.ttr_stage.initialize_and_positionTTR, args=[self.tip, self.tilt, self.rotate])
        self.ttr_thread.start()
        super().initialize_hardware()
        self.ttr_thread.join()
        if self.ttr_thread.exception is not None:
            log.error("TTR stage failed to initialize!")
            self.failed_hardware["TTR stage"] = self.ttr_stage

    def pre_exposure_tasks(self, settings, light_engine):
        if self.ttr_stage.config_dict.get("auto_repositioning", True):
            self.tip = None
            self.tilt = None

            last_positions = get_last_calibration_positions_from_logs()
            matching_keys = [key for key in last_positions if "_tip" in str(key) or "_tilt" in str(key)]
            if len(matching_keys) == 0:
                self.tip = last_positions.get("tip",None)
                self.tilt = last_positions.get("tilt",None)
            self.rotate = last_positions.get(f"rotate",None)

            if self.tip is None:
                self.tip = last_positions.get(f"{light_engine}_tip_base",0)
                self.tip += last_positions.get(f"{light_engine}_tip_offset",0)
            if self.tilt is None:
                self.tilt = last_positions.get(f"{light_engine}_tilt_base",0)
                self.tilt += last_positions.get(f"{light_engine}_tilt_offset",0)

            if self.tip is not None:
                self.tip /= 1000
            if self.tilt is not None:
                self.tilt /= 1000
            if self.rotate is not None:
                self.rotate /= 1000

            self.ttr_threads = self.ttr_stage.threadedTTRMove(log, self.tip, self.tilt, self.rotate, join=False)
        return super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, light_engine):
        """Join Focus threads"""
        if self.ttr_threads is not None:
            for thread in self.ttr_threads:
                if thread is not None:
                    thread.join()
                    if thread.exception is not None:
                        log.warning("Unable to move TTR stage")
                        self.failed_hardware["TTR Stage"] = self.ttr_stage
                        raise PrintingException()
            self.ttr_threads = None
        return super().pre_exposure_joins(light_engine)

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self):
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            try:
                self.ttr_stage.logging_start()
            except Exception as ex:
                log.critical("Unable to communicate with ttr stage (%s)", ex, exc_info=True)
                self.failed_hardware["TTR Stage"] = self.ttr_stage
                raise PrintingException()
            super().planarization_step_1()

    @run_in_thread("initialized", "Cancel Planarization")
    def cancel_planarization(self):
            try:
                self.ttr_stage.logging_stop()
            except Exception as ex:
                log.critical("Unable to communicate with ttr stage (%s)", ex, exc_info=True)
                self.failed_hardware["TTR Stage"] = self.ttr_stage
                raise PrintingException()
            super().cancel_planarization()
        
    def finish_print(self):
        try:
            self.ttr_stage.logging_stop()
            time.sleep(0.1)
            self.ttr_stage.setup_log_file(None)
        except Exception as ex:
            log.critical("Unable to communicate with ttr stage (%s)", ex, exc_info=True)
            self.failed_hardware["TTR Stage"] = self.ttr_stage
            raise PrintingException()
        super().finish_print()