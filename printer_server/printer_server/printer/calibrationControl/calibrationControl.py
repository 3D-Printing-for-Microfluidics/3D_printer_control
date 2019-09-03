import RPi.GPIO as GPIO
import time
from .kdc101_stage import KDC101

import serial
import serial.tools.list_ports

class CalibrationControl:
    def __init__(self):
        self.motors = ["Tip", "Tilt", "Distance"]
        self.tipTilt = TipTilt_stage()
        # self.dist = KDC101()
        self.tipTilt.initialize()
        # self.dist.initialize()
        print("__init__ calibration Done")

    def initialize(self): 
        self.tipTilt.initialize()
        # self.dist.initialize()
    
    def move(self, axis, um):
        if axis == "Distance":
            self.dist.move(um)
        else:
            self.tipTilt.move(axis, um)



class TipTilt_stage(serial.Serial): 

    def __init__(self):
        super().__init__(baudrate=115200, timeout=None)
        # Button parameters 
        self.motors = ["Tip","Tilt"] # if you add a motor here, make sure to add it's pins below 
        self.location = '1-1.1.3'

    def initialize(self):
        self.connect()
        self.send('$X')     # Disable homing necessity
        self.send('G91')    # Send relative mode    

    def connect(self):
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            if 'ttyUSB' in p.name:
                print("Found", p.device, p.location)
                if p.location == self.location:
                    print(p.device)
                    self.port = p.device

        if self.port is None:
            raise ValueError('Tip Tilt not found')
        elif self.is_open:
            self.close()
        self.open()
        return self.send("G4 P0")

    def move(self, axis, um):
        mm = um / 1000
        speed = 10  #mm/min
        if(axis == 'Tip'):
            axis = 'X'
        else:
            axis = 'Y'
        command = 'G1 ' + axis + str(mm) + ' F' + str(speed)
        print(command)
        self.send(command)

    def send(self, cmd):
        # send the command to grbl
        response = self.transmit(cmd)
        
        # send a G4 P0 command to wait for completion of previous command 
        self.transmit('G4 P0')  

        # return the reponse of the first command 
        return response

    def transmit(self, cmd):
        self.write(bytes(cmd + '\r', encoding='ascii')) # write to serial tx buffer 
        return self.receive()                           # wait for response from serial rx buffer

    def receive(self):
        response = b''
        response += self.readline()     # wait for the first line to fill in the rx buffer 
        while self.in_waiting:          # while there is more data in the rx buffer      
            response += self.readline() # read next line from rx buffer 
        return response.decode()        # return decoded byte response (as string)

    def test_sequence(self):
        pass



if __name__ == '__main__':
    c=CalibrationControl()
    c.test_sequence()
