# -*- coding: utf-8 -*-
"""Solus module."""
import serial
import serial.tools.list_ports
import serial.serialutil
import re
import time

__all__ = ['Solus']


class Solus(serial.Serial):
    def __init__(self, hwid, verbose=False):
        super().__init__(baudrate=115200, timeout=None)
        self.verbose = verbose
        self.hwid = hwid
        self.regex = re.compile(r'^(BP|QW) (UP|DOWN) (-?\d+(\.\d+)?) SPEED (\d+)')
        
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
        return self.receive()
        
    def goToZmax(self):
        response =  self.send('G90')          # set positioning to absolute
        response += self.send('G1 Z-65 F800') # send the platform to 65 mm above the quartz
        return response

    def initialize(self):
        response =  self.send('$H')           # calibrate the axes     
        response =  self.send('G90')          # set positioning to absolute
        response += self.send('G21')          # set unit to mm
        response += self.send('G1 X-3 F300')  # set unit to mm
        response += self.goToZmax()           # go to top position
        return response
        
    def goToZmin(self):
        return self.send('G1 Z0 F800')   # send the platform to 0 
        
    def goToFirstLayerHeight(self, height):
        response =  self.send('G1 Z-{:.4f} F600'.format(height))        
        response += self.send('G91')    # set positioning to relative
        return response
        
    def printCycle(self, layerThicknessMm, commandChain):
        # TODO: explain the code here
        for i in range(len(commandChain)-1, -1, -1):
            if commandChain[i].startswith('BP'):
                a = i
                break
            if i == 0:
                a = -1
                
        if a == -1:
            commandChain.append('BP UP {:.4f} SPEED 400'.format(layerThicknessMm))
        else:
            lastBpCommand = commandChain[a].split()
            distance = float(lastBpCommand[2])
            speed = lastBpCommand[4]
            if lastBpCommand[1] is 'UP':
                newCommand = 'BP UP {:.4f} SPEED {}'.format(distance+layerThicknessMm, speed)
            else:
                newCommand = 'BP DOWN {:.4f} SPEED {}'.format(distance-layerThicknessMm, speed)
            commandChain[a] = newCommand
            
        for command in commandChain:
            self.execute(command)
            
    def execute(self, command):
        # Example: `WAIT 1.5` => `time.sleep(1.5)`
        if command.startswith('WAIT'):
            time.sleep(float(command.split()[1]))
            return
            
        m = self.regex.fullmatch(command)
        if m:
            direction = m.group(2)
            distance = float(m.group(3))
            speed = int(m.group(5))
            if m.group(1) == 'BP':
                self.moveZ(direction, distance, speed)
            elif m.group(1) == 'QW':
                self.moveX(direction, distance, speed)
                
    def pause(self):
        """What solus does after a print is paused"""
        return self.send('G1 Z30 F400')
        
    def resume(self, layerThickness):
        """Resume after pausing"""
        return self.send('G1 Z-{:.4f} F400'.format(30-layerThickness))
        
    def moveX(self, direction, distance, speed):
        """Move quartz window up/down a certain distance at a 
        given speed. 
        
        :param str direction: can only be 'UP' or 'DOWN'
        :param distance: distance in millimeters.
        :param speed: Always treated as positive. The unit is mm/min.
        """
        if direction == 'UP':
            distance = -distance
        return self.send('G1 X{:.4f} F{:d}'.format(distance, abs(speed)))
        
    def moveZ(self, direction, distance, speed):
        """Move build platform up/down a certain distance at a 
        given speed. 
        
        :param str direction: can only be 'UP' or 'DOWN'
        :param distance: distance in millimeters.
        :param speed: Always treated as positive. The unit is mm/min.
        """
        if direction == 'UP':
            distance = -distance
        return self.send('G1 Z{:.4f} F{:d}'.format(distance, abs(speed)))
        
    def send(self, cmd):
        # send the command to grbl
        if self.verbose: print('Sent: ' + cmd)
        response = self.transmit(cmd)
        if self.verbose: print("Response: ", response)
        
        # send a G4 P0 command to wait for completion of previous command 
        self.transmit('G4 P0\r')

        # return the reponse of the first command 
        return response

    def transmit(self,cmd):
        self.write(bytes(cmd + '\r', encoding='ascii')) # write to serial tx buffer 
        return self.receive()                           # wait for response from serial rx buffer
        
    def receive(self):
        response = b''
        response += self.readline()     # wait for the first line to fill in the rx buffer 
        while self.in_waiting:          # while there is more data in the rx buffer      
            response += self.readline() # read next line from rx buffer 
        return response.decode()        # return decoded byte response (as string)

    def __del__(self):
        try:
            self.goToZmax()
            self.close()
        except serial.serialutil.SerialException:
            pass

def findUsbPort(hwid):
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
            if 'ttyUSB' in p.name:
                print("Found", p.device)
                if hwid in p.hwid:
                    return p.device

if __name__ == '__main__':
    s = Solus('1A86:7523')
    print("CONNECT")
    s.connect()
    print("INITIALIZE")
    s.initialize()
    print("GO TO Z MIN")
    s.goToZmin()
    print("GO TO Z MAX")
    s.goToZmax()



    commandChain= [
          "WAIT 0.1",
          "BP UP 1 SPEED 400",
          "QW DOWN 3 SPEED 300",
          "WAIT 1.5",
          "BP UP 2 SPEED 400",
          "QW UP 3 SPEED 300",
          "BP DOWN 3 SPEED 400",
          "WAIT 1.5"
        ]

    print("GO TO 1mm")
    s.goToFirstLayerHeight(0.1)

    for i in range(0,3):
        s.printCycle(0.1, commandChain)




    print("DONE")
