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
        self.tip = get_last_calibration_positions_from_logs().get("tip",None)
        self.tilt = get_last_calibration_positions_from_logs().get("tilt",None)
        self.rotate = get_last_calibration_positions_from_logs().get("rotate",None)
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


    def pre_print_tasks(self):
        if self.ttr_stage.config_dict.get("auto_repositioning", True):
            self.tip = get_last_calibration_positions_from_logs().get("tip",None)
            self.tilt = get_last_calibration_positions_from_logs().get("tilt",None)
            self.rotate = get_last_calibration_positions_from_logs().get("rotate",None)
            if self.tip is not None:
                self.tip /= 1000
            if self.tilt is not None:
                self.tilt /= 1000
            if self.rotate is not None:
                self.rotate /= 1000
            self.ttr_threads = self.ttr_stage.threadedTTRMove(log, self.tip, self.tilt, self.rotate, join=False)
        super().pre_print_tasks()

    def pre_print_joins(self):
        if self.ttr_stage.config_dict.get("auto_repositioning", True):
            if self.ttr_threads is not None:
                for thread in self.ttr_threads:
                    thread.join()
                    if thread.exception is not None:
                        log.warning("Unable to move TTR stage")
        super().pre_print_joins()

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