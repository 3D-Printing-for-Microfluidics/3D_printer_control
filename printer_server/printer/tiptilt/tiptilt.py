import atexit
import serial
import serial.tools.list_ports
import serial.serialutil

def findUsbPort(hwid):
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if hwid in p.hwid:
            print("Found '{}' at '{}'".format(p.hwid, p.device))
            return p.device
    return None             # not found

class TipTilt(serial.Serial):

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

    def connect(self):
        self.port = findUsbPort(self.hwid)
        if self.port is None:
            raise ValueError('Tip/Tilt not found')
        if self.is_open:
            self.close()
        self.open()
        self.reset_input_buffer()
        self.reset_output_buffer()
        print("Connected to", self.port)
        self.send("G4 P0")  # send a G4 P0 command so you get a response, even if the startup message doesn't appear
        self.send('$X')     # unlock (starts in alarm mode)
        self.send('G91')    # set to relative mode
        return self.send("G4 P0")

    def home(self):
        self.send("$H")

    def move(self, axis, distance_um, speed=100, relative=True):
        """
        Move the specified number of um at the specified speed (in mm/min)
        """
        distance_mm = distance_um / 1000                                            # convert um to mm
        axis = 'X' if axis == 'Tip' else 'Y'                                        # convert Tip/Tilt to X/Y
        _ = self.send("G91") if relative else self.send("G90")                      # set absolute or relative mode
        return self.send('G1 {}{:.4f} F{:d}'.format(axis, distance_mm, abs(speed))) # send motion command

    def send(self, cmd):
        # send the command to grbl
        if self.verbose: print('Sent: ' + cmd)
        response = self.transmit(cmd)
        if self.verbose: print("Response: ", response)
        self.transmit('G4 P0')              # send a G4 P0 command to block on completion of previous command
        self.status = self.transmit("?")    # update status after each command is complete
        return response                     # return the response of the main command

    def transmit(self, cmd):
        self.write(bytes(cmd + '\r', encoding='ascii')) # write to serial tx buffer
        return self.receive()                           # wait for response from serial rx buffer

    def receive(self):
        response = b''
        response += self.readline()         # wait for the first line to fill in the rx buffer
        while self.in_waiting:              # while there is more data in the rx buffer
            response += self.readline()     # read next line from rx buffer
        return response.decode().rstrip()   # return decoded byte response (as string) without traililng newline
