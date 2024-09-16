import logging

from printer_server.threading_wrapper import Thread
from printer_server.hardware_configuration.hardware_configuration import driver_handles
from printer_server.printer_control.print_control import PrintControl
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

    def connect_hardware(self):
        self.ttr_thread = Thread(log, name="ttr_control_connect_thread", target=self.ttr_stage.connect, args=[self.shutdown])
        self.ttr_thread.start()
        super().connect_hardware()
        self.ttr_thread.join()
        if not self.ttr_stage.connected:
            log.error("TTR stage failed to connect!")
            self.failed_hardware["TTR stage"] = self.ttr_stage
            self.all_hardware_connected = False

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
            self.ttr_thread = self.ttr_stage.threadedTTRMove(log, self.tip, self.tilt, self.rotate, join=False)
        super().pre_print_tasks()

    def pre_print_joins(self):
        if self.ttr_stage.config_dict.get("auto_repositioning", True):
            if self.ttr_thread is not None:
                self.ttr_thread.join()
        super().pre_print_joins()