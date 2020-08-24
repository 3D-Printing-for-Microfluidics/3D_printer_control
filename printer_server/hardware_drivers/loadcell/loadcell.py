import atexit
import serial
import serial.tools.list_ports
import serial.serialutil
import threading
import os

import logging

class LoadCellDeviceControl(serial.Serial):
    def __init__(self, hwid='PID=16C0:0483 SER=6256240', log_level=logging.DEBUG):
        super().__init__(baudrate=115200, timeout=1)
        self.log_level = log_level
        self.hwid = hwid
        self.port = None                # start with no port
        self.status = None              # status to be updated after every send
        
    def findUsbPort(self, hwid):
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            if hwid.upper() in p.hwid:
                self.log.debug("Found '%s' at '%s'", p.hwid, p.device)
                return p.device
        return None             # not found

    def connect(self):
        self.port = self.findUsbPort(self.hwid)
        if self.port is None:
            raise ValueError('Load cell not found')
        if self.is_open:
            self.close()
        self.open()
        self.flushInput()
        self.flushOutput()
        self.log.info("Connected to {}", self.port)
        #print("Connected to", self.port)
        
        atexit.register(self.close)

    def set_gain(self, value):
        """
        Set the gain
        """
        self.log.info("Gain set to {}", value)
        #print("gain set to {}", value)
        return self.send('g {}'.format(value)), value

    def set_filter_corner(self, value):
        """
        Set the filter 3d corner
        """
        self.log.info("Corner set to {}", value)
        #print("corner set to {}", value)
        return self.send('f {}'.format(value)), value

    def set_sample_period(self, period_us):
        """
        Set the sampling period to period_us (in microseconds)
        """
        self.log.info("Period set to {}", period_us)
        #print("period set to {}", period_us)
        return self.send('p {}'.format(period_us)), period_us

    def sample(self):
        """
        Sample the specified channel (0,1) for num_samples at a period of period_us (in microseconds)
        """
        return self.send('b')

    def stop(self, channel=0):
        """
        Sample the specified channel (0,1) for num_samples at a period of period_us (in microseconds)
        """
        return self.send('e')

    def send(self, cmd):
        self.log.debug("Sent: {}", cmd)
        #if self.verbose: print('Sent: ' + cmd)
        self.write(bytes(cmd + '\n', encoding='ascii')) # write to serial tx buffer
        response = self.receive()
        self.log.debug("Response: {}", response)
       # if self.verbose: print("Response: ", response)
        return response                                 # return the response to the command

    def receive(self):
        response = b''
        response += self.readline()         # wait for the first line to fill in the rx buffer
        return response.decode().rstrip()   # return decoded byte response (as string) without traililng newline
        
    def receiveAll(self):
        response = b''
        response += self.readline()         # wait for the first line to fill in the rx buffer
        while self.in_waiting:              # while there is more data in the rx buffer
            response += self.readline()     # read next line from rx buffer
        return response.decode().rstrip()   # return decoded byte response (as string) without traililng newline

class LoadCell:
    def __init__(self):
        self.running = False
        self.thread = threading.Thread(target=self.loop)
        self.raws = []
        self.cell = LoadCellDeviceControl(v)
        
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

    def start(self, filename):
        self.log_file = filename
        
        self.cell.connect()
        self.cell.set_sample_period(1000)
        self.cell.set_gain(100)
        self.cell.set_filter_corner(1000)
        
        self.running = True
        self.raws = []
        if not self.thread.is_alive():
            self.thread.start()

    def stop(self):
        try:
            self.cell.stop()
        except serial.SerialException:
            pass
        self.running = False

    def getData(self):
        from pathlib import Path
        from datetime import datetime
        import os

        raw = ""

        try:
            raw = self.cell.receive()
        except serial.SerialException:
            self.running = False
        else:
            self.raws.append(raw)

    def adcToForce(self, x):
        slope = -1.46
        intercept = 33845.0

        grams = (x - intercept)/slope
        n = grams/1000*9.8
        return n

    def loop(self):
        from pathlib import Path
        from datetime import datetime
        import os

        #create our load cell object
        #c = LoadCell()

        #connect to it and set our gain
        
        if(self.running):

            #print header
            with open(self.log_file, "a") as f:
                f.write("Index\tMicroseconds\tRaw\tNewtons\tAvg\n")

            #sample until running is set to false
            self.cell.flushInput()
            self.cell.sample()
            while(self.running):
                self.getData()
                
            with open(self.log_file, "a") as f:
                length = len(self.raws)
                windowSize = 10
                windowData = []
                for i in range(length - 2):
                    splitData = self.raws[i].split(",")
                    if(len(splitData) > 2):
                        index = splitData[0]
                        microseconds = splitData[1]
                        data = splitData[2]

                        try:
                            index = int(index)
                            microseconds = float(microseconds)
                            data = float(data)
                            force = self.adcToForce(data)
                        except ValueError:
                            self.log.warning("Unable to parse loadcell data: {}", self.raws[i])
                            print(self.raws[i])
                            continue
                            
                        if len(windowData) >= windowSize:
                            windowData.pop(0)
                        windowData.append(force)
                        
                        if len(windowData) == windowSize:
                            avg = 0
                            for i in windowData:
                                avg += i
                            avg = avg / windowSize
                            f.write("{}\t{}\t{}\t{}\t{}\n".format(index, microseconds, data, force, avg))
                        else:
                            f.write("{}\t{}\t{}\t{}\t\n".format(index, microseconds, data, force))

    

