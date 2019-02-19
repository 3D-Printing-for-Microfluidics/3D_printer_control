# -*- coding: utf-8 -*-
"""Solus module."""
import serial
import serial.tools.list_ports
import serial.serialutil
import re
import time

__all__ = ['Solus']


class Solus(serial.Serial):
    def __init__(self, hwid, verbose=True):
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
        return self.send("G4 P0")   # send a G4 P0 command so you get a response, even if the startup message doesn't appear 
        
    def goToZmax(self):
        response =  self.send('G90')          # set positioning to absolute
        # response += self.send('G1 Z-65 F800') # send the platform to 65 mm above the quartz
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
        # send the platform to 0 
        response = self.send('G1 Z-20 F800')
        response = self.send('G1 Z0 F100')
        return response
        
    def goToFirstLayerHeight(self, height):
        response =  self.send('G1 Z-{:.4f} F600'.format(height))        
        response += self.send('G91')    # set positioning to relative
        return response
        
    def printCycle(self, layerThicknessMm, commandChain):
        # Command chain is the series of commands for this layer 
        # i.e. ['WAIT 0.1', 'BP UP 1 SPEED 400', 'QW DOWN 3 SPEED 300', 'WAIT 1.0', 
        #       'BP UP 2 SPEED 400', 'QW UP 3 SPEED 300', 'BP DOWN 3.00 SPEED 400', 'WAIT 1.0']

        # find the index of the last BP command and save it. -1 means there was none 
        lastBPindex = -1
        for i in range(0,len(commandChain)):
            if commandChain[i].startswith('BP'):
                lastBPindex = i                     

        # alter the last BP command (take off layer thickness), execute all others 
        for i in range(0,len(commandChain)):
            if i == lastBPindex:                
                lastBpCommand = commandChain[lastBPindex].split()
                distance = float(lastBpCommand[2])
                speed = lastBpCommand[4]
                newCommand = 'BP DOWN {:.4f} SPEED {}'.format(distance-layerThicknessMm, speed)
                self.execute(newCommand)
            else:
                self.execute(commandChain[i])
            
        # move up by layerThicknessMm if no BP command was supplied 
        if lastBPindex ==-1:
            self.execute('BP UP {:.4f} SPEED 400'.format(layerThicknessMm)) 
            
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
        return self.moveZ('UP', 5, 400)
        
    def resume(self, layerThickness):
        """Resume after pausing"""
        return self.moveZ('DOWN', 5-layerThickness, 400)
        
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
        
    def queryPosition(self):
        # query position and capture response 
        if self.verbose: print('Sent: ' + '?')
        return self.transmit('?')

    def send(self, cmd):
        # send the command to grbl
        if self.verbose: print('Sent: ' + cmd)
        response = self.transmit(cmd)
        if self.verbose: print("Response: ", response)
        
        # send a G4 P0 command to wait for completion of previous command 
        self.transmit('G4 P0')  
        
        # print current position if in verbose mode 
        if self.verbose: print("position: ", self.queryPosition())

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
          "BP UP 1 SPEED 300",
          "QW DOWN 3 SPEED 300",
          "WAIT 1.5",
          "BP UP 2 SPEED 300",
          "QW UP 3 SPEED 300",
          "BP DOWN 3 SPEED 300",
          "WAIT 1.5"
        ]
        
    print("GO TO 1mm")
    s.goToFirstLayerHeight(0.1)

    print(commandChain)
    for i in range(0,5):
        print("Layer", i)
        s.printCycle(.01, commandChain)

    print("DONE")