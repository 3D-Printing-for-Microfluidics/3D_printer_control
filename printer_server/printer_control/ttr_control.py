from printer_server.printer_control.print_control import *

class TTRControl(PrintControl):
    def __init__(self):
        super().__init__()

        # hardware handles
        self.tiptilt = driver_handles.tiptilt
        
    def connect_hardware(self):
        ret = self.tiptilt.connect()
        super().connect_hardware()
        if not self.tiptilt.connected:
            self.all_hardware_connected = False