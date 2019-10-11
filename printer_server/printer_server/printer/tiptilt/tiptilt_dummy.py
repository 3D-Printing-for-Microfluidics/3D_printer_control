import atexit
import serial
import serial.tools.list_ports
import serial.serialutil

class TipTilt_dummy(serial.Serial):

    def __init__(self, hwid='1A86:7523', verbose=True):
        super().__init__(baudrate=115200, timeout=None)
        # Button parameters
        self.motors = ["Tip", "Tilt"] # if you add a motor here, make sure to add it's pins below
        self.location = '1-1.3'
        self.verbose = verbose
        self.hwid = hwid
        self.port = None                # start with no port
        self.status = None              # status to be updated after every send
        atexit.register(self.close)
        print(" tiptilt - __init__({},{})".format(hwid, verbose))

    def connect(self):
        print(" tiptilt - connect()")

    def home(self):
        print(" tiptilt - home()")

    def move(self, axis, distance_um, speed=10):
        # """
        # Move the specified number of um at the specified speed (in mm/min)
        # """
        print(" tiptilt - move({},{},{})".format(axis, distance_um, speed))

    def send(self, cmd):
        # send the command to grbl
        print(" tiptilt - send({})".format(cmd))

    def transmit(self, cmd):
        pass

    def receive(self):
        return ""
