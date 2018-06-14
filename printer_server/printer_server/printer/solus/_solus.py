import serial
import serial.tools.list_ports
import serial.serialutil
import re
import time

__all__ = ['Solus']


class Solus(serial.Serial):
    def __init__(self, serialNum):
        super().__init__(baudrate=115200, timeout=0)
        self.serialNum = serialNum
        self.regex = re.compile(r'^(BP|QW) (UP|DOWN) (-?\d+(\.\d+)?) SPEED (\d+)')
        
    def findUsbPort(self):
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            if 'Arduino Uno' in p.description:
                if p.serial_number == self.serialNum:
                    self.port = p.device
                    
    def connect(self):
        self.findUsbPort()
        if self.port is None:
            raise ValueError('Solus not found')
        elif self.is_open:
            self.close()
        self.open()
        self.flushInput()
        self.flushOutput()
        # must wait for 2 seconds to connet
        time.sleep(2)
        
    def homing(self):
        #set positioning to absolute
        res = self.send('G90')
        #send the platform to 90 mm above the quartz
        res += self.send('G1 Z90 F800')
        time.sleep(self.calcWaitTime(90, 800))
        return res
        
    def initializeBuildPlatform(self):
        #planarize the axises
        res = self.send('$h')
        time.sleep(11)
        #set unit to mm
        res += self.send('G21')
        res += self.homing()
        return res
        
    def goToZeroZ(self):
        res = self.send('G1 Z0 F800')
        time.sleep(self.calcWaitTime(90, 800))
        return res
        
    def goToFirstLayerHeight(self, height):
        res = self.send('G1 Z{:.4f} F600'.format(height))
        #set positioning to relative
        res += self.send('G91')
        # wait extra 1 s before exposing the 1st layer
        time.sleep(self.calcWaitTime(90, 600) + 1)
        return res
        
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
        res = self.send('G1 Z30 F400')
        time.sleep(self.calcWaitTime(30, 400))
        return res
        
    def resume(self, layerThickness):
        """Resume after pausing"""
        res = self.send('G1 Z-{:.4f} F400'.format(30-layerThickness))
        time.sleep(self.calcWaitTime(30, 400))
        return res
        
    def moveX(self, direction, distance, speed):
        """Move quartz window up/down a certain distance at a 
        given speed. 
        
        :param str direction: can only be 'UP' or 'DOWN'
        :param distance: distance in millimeters.
        :param speed: Must be positive. The unit is mm/min.
        """
        if direction is 'UP':
            distance = -distance
            
        self.send('G1 X{:.4f} F{:d}'.format(distance, abs(speed)))
        time.sleep(self.calcWaitTime(distance, speed))
        
    def moveZ(self, direction, distance, speed):
        """Move build platform up/down a certain distance at a 
        given speed. 
        
        :param str direction: can only be 'UP' or 'DOWN'
        :param distance: distance in millimeters.
        :param speed: Must be positive. The unit is mm/min.
        """
        if direction is 'DOWN':
            distance = -distance
            
        self.send('G1 Z{:.4f} F{:d}'.format(distance, abs(speed)))
        time.sleep(self.calcWaitTime(distance, speed))
        
    def send(self, command):
        """Send command through USB
            
            command: '$h'   response: b'Grbl 0.9g ...'
            other commands  response: b'ok\r\n'
        """
        self.write(bytes(command + '\r', encoding='ascii'))
        response = ''
        while self.inWaiting():
            response += self.readline().decode()
        return response
        
    def calcWaitTime(self, distance, speed):
        """Because there is no feedback after **Solus** moves its 
        stages, we don't know when exactly the stages finish movement. 
        In order to synchronize all parts in 3D printer, we have to 
        manually set a wait time. This method is to calculate this 
        wait time using the stage travel distance and speed. 

        :param distance: stage travel distance in mm
        :param speed: stage travel speed in mm/min
        :returns: wait time in seconds
        :rtypes: float
        """
        return abs(distance/speed * 60)

    def __del__(self):
        try:
            self.homing()
            self.close()
        except serial.serialutil.SerialException:
            pass
