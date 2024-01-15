from printer_server.printer_control.print_control import *

class TTRControl(PrintControl):
    def __init__(self):
        super().__init__()

        # hardware handles
        self.ttr_stage = driver_handles.ttr_stage

    def connect_hardware(self):
        ttr_thread = Thread(log, name="ttr_control_setup_thread", target=self.ttr_stage.connect, args=[self.shutdown])
        ttr_thread.start()
        super().connect_hardware()
        ttr_thread.join()
        if not self.ttr_stage.connected:
            self.all_hardware_connected = False

    def initalize_hardware(self):
        pass
        # ttr_pos = 
        # ttr_thread = self.focus_stage.initialize_and_positionTTR(ttr_pos, join=False)
        # super().initalize_hardware()
        # if ttr_thread is not None:
        #     ttr_thread.join()
        # self.ttr_thread.initialized = True