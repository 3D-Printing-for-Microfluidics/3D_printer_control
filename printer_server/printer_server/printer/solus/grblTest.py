import serial
import serial.tools.list_ports
import serial.serialutil

def findUsbPort(hwid):
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
            if 'ttyUSB' in p.name:
                print("Found", p.device)
                if hwid in p.hwid:
                    return p.device

class BuildStage(serial.Serial):
    def __init__(self, hwid, verbose=False):
        super().__init__(baudrate=115200, timeout=None)
        self.verbose = verbose
        self.hwid = hwid
        # self.regex = re.compile(r'^(BP|QW) (UP|DOWN) (-?\d+(\.\d+)?) SPEED (\d+)')

    def connect(self):
        self.port = findUsbPort(self.hwid)
        if self.port is None:
            raise ValueError('BP and QW not found')
        elif self.is_open:
            self.close()
        print("Connecting to", self.port, "...")
        self.open()
        self.reset_input_buffer()
        self.reset_output_buffer()
        return self.send("G4 P0") 