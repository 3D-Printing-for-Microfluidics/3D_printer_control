import logging

from printer_server.threading_wrapper import Thread
from printer_server.hardware_configuration import driver_handles
from printer_server.printer_control.print_control import PrintControl

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class TTRControl(PrintControl):
    def __init__(self):
        super().__init__()

        # hardware handles
        self.ttr_stage = driver_handles.ttr_stage

    def connect_hardware(self):
        self.ttr_thread = Thread(log, name="ttr_control_setup_thread", target=self.ttr_stage.connect, args=[self.shutdown])
        self.ttr_thread.start()
        super().connect_hardware()
        self.ttr_thread.join()
        if not self.ttr_stage.connected:
            log.error("TTR stage failed to connect!")
            self.all_hardware_connected = False

    def initialize_hardware(self):
        super().initialize_hardware()
        # ttr_pos = 
        # self.ttr_thread = self.focus_stage.initialize_and_positionTTR(ttr_pos, join=False)
        # super().initialize_hardware()
        # if self.ttr_thread is not None:
        #     self.ttr_thread.join()
        # self.ttr_stage.initialized = True