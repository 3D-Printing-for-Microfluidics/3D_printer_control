import serial
import serial.tools.list_ports
import time
import platform

__all__ = ['Solus']

class Solus(serial.Serial):
    def __init__(self, verbose=False):
        super().__init__(baudrate=115200, timeout=None)
        self.verbose = verbose

    def connect(self):
        self.port = findUsbPort()
        if self.port is None:
            raise ValueError('X and Z stages not found')
        elif self.is_open:
            self.close()
        print("Connecting to", self.port, "...")
        self.open()
        self.flushInput()
        self.flushOutput()
        self.receive()

    def initialize(self):
        self.send('$H')     # calibrate the axes     
        self.send('G21')    # set unit to mm
        self.goToZmax()     # go to top position

    def goToZmax(self):
        self.send('G90')          # set positioning to absolute
        # self.send('G1 Z-65 F800') # send the platform to 65 mm above the quartz
        self.send('G1 Z-20 F800') # send the platform to 65 mm above the quartz

    def goToZmin(self):
        self.send('G1 Z0 F800')   # send the platform to 0 

    def goToFirstLayerHeight(self, height):
        self.send('G1 Z-{:.4f} F600'.format(height))        
        self.send('G91')    # set positioning to relative

    def printCycle(self, params):
        # d0 (mm): quartz window tilting distance after each exposure
        # sx0: quartz window tilting down speed
        # sx1: quartz window tilting up speed
        # dz0 (um): build platform moving distance after each exposure but before quartz window tilts
        # dz1 (um): build platform moving distance after each exposure after quartz window tilts
        # sz0 (mm/min): build platform moving up speed
        # sz1 (mm/min): build platform moving down speed

        # this only works in versions <= python 3.6
        d0, sx0, sx1, dz0, dz1, sz0, sz1, layerThickness = params

        self.send('G1 Z{:.4f} F{:d}'.format(dz0/1000, sz0))
        self.send('G1 X{:d} F{:d}'.format(d0, sx0))
        self.send('G1 Z{:.4f} F{:d}'.format(dz1/1000, sz0))
        self.send('G1 X-{:d} F{:d}'.format(d0, sx1))
        self.send('G1 Z-{:.4f} F{:d}'.format((dz0+dz1-layerThickness)/1000, sz1))

    def transmit(self,cmd):
        self.write(bytes(cmd + '\r', encoding='ascii')) # write to serial tx buffer 
        return self.receive()                           # wait for response from serial rx buffer
    
    def send(self, cmd):
        # send the command to grbl
        if self.verbose: print('Sent: ' + cmd)
        response = self.transmit(cmd)
        if self.verbose: print("Response: ", response)
        
        # send a G4 P0 command to wait for completion of previous command 
        self.transmit('G4 P0\r')

        # return the reponse of the first command 
        return response

    def receive(self):
        response = b''
        response += self.readline()     # wait for the first line to fill in the rx buffer 
        while self.inWaiting():         # while there is more data in the rx buffer      
            response += self.readline() # read next line from rx buffer 
        return response.decode()        # return decoded byte response 

    def __del__(self):
        try:
            # self.goToZmax()
            self.close()
        except serial.serialutil.SerialException:
            pass

def findUsbPort():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
            # import pdb; pdb.set_trace()
            if 'ttyUSB' in p.name:
                print("Found", p.device)
                if '1A86:7523' in p.hwid:
                    return p.device

if __name__ == '__main__':
    s = Solus(verbose=True)
    print("CONNECT")
    s.connect()
    print("INITIALIZE")
    s.initialize()
    print("GO TO Z MIN")
    s.goToZmin()
    print("GO TO 10mm")
    s.goToFirstLayerHeight(10)
    print("DONE")