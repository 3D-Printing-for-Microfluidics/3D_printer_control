import atexit
import serial
import serial.tools.list_ports
import serial.serialutil
import threading

import logging

class LoadCellDeviceControl(serial.Serial):
    """
    Class handling direct communication with loadcell
    """
    def __init__(self, hwid='PID=16C0:0483 SER=6256240', log_level=logging.DEBUG):
        """
        Initializes the loadcell controller
        """
        super().__init__(baudrate=115200, timeout=1)
        self.log_level = log_level
        self.hwid = hwid
        self.port = None                # start with no port
        self.status = None              # status to be updated after every send
        
    def findUsbPort(self, hwid):
        """
        Finds serial port with given hwid
        
        Parameters:
            hwid - device identifier
        """
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            if hwid.upper() in p.hwid:
                self.log.debug("Found '%s' at '%s'", p.hwid, p.device)
                return p.device
        return None             # not found

    def connect(self):
        """
        Opens a serial handle to the loadcell device
        """
        self.port = self.findUsbPort(self.hwid)
        if self.port is None:
            raise ValueError('Load cell not found')
        if self.is_open:
            self.close()
        self.open()
        self.flushInput()
        self.flushOutput()
        self.log.debug("Connected to {}", self.port)
        #print("Connected to", self.port)
        
        atexit.register(self.close)

    def set_gain(self, value):
        """
        Set the gain
        """
        self.log.debug("Gain set to {}", value)
        #print("gain set to {}", value)
        return self.send('g {}'.format(value)), value

    def set_filter_corner(self, value):
        """
        Set the filter 3d corner
        """
        self.log.debug("Corner set to {}", value)
        #print("corner set to {}", value)
        return self.send('f {}'.format(value)), value

    def set_sample_period(self, period_us):
        """
        Set the sampling period to period_us (in microseconds)
        """
        self.log.debug("Period set to {}", period_us)
        #print("period set to {}", period_us)
        return self.send('p {}'.format(period_us)), period_us

    def sample(self):
        """
        Sample at a period of period_us (in microseconds)
        """
        return self.send('b')

    def stop(self, channel=0):
        """
        Stop sampling
        """
        return self.send('e')

    def send(self, cmd):
        """
        Sends serial command to the loadcell device
        """
        self.log.debug("Sent: {}", cmd)
        #if self.verbose: print('Sent: ' + cmd)
        self.write(bytes(cmd + '\n', encoding='ascii')) # write to serial tx buffer
        response = self.receive()
        self.log.debug("Response: {}", response)
       # if self.verbose: print("Response: ", response)
        return response                                 # return the response to the command

    def receive(self):
        """
        Sends serial response from the loadcell device
        """
        response = b''
        response += self.readline()         # wait for the first line to fill in the rx buffer
        return response.decode().rstrip()   # return decoded byte response (as string) without traililng newline
        
#    def receiveAll(self):
#        response = b''
#        response += self.readline()         # wait for the first line to fill in the rx buffer
#        while self.in_waiting:              # while there is more data in the rx buffer
#            response += self.readline()     # read next line from rx buffer
#        return response.decode().rstrip()   # return decoded byte response (as string) without traililng newline

class LoadCell:
    """
    Class providing high level control of loadcell
    """
    def __init__(self, period=1000, filter_corner=1000):
        """
        Initializes the loadcell
        """
        self.running = False
        self.raws = []
        self.period = period
        self.filter_corner = filter_corner
        self.thread = threading.Thread(target=self.loop)
        
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        
        self.cell = LoadCellDeviceControl()
        self.cell.log = self.log
        
    def connect(self):
        """
        Connects to the loadcell and sets parameters.
        """
        self.cell.connect()
        self.cell.set_sample_period(int(self.period))
        self.cell.set_gain(100)
        self.cell.set_filter_corner(int(self.filter_corner))

    def start(self, filename):
        """
        Starts the loadcell collecting data
        
        Parameters:
            filename    - local path and filename (current_job/loadcell_data.txt)
            period      - sample period of loadcell (in milliseconds)
            corner      - corner frequency of loadcell highpass filter (in Hz)
        """
        if not self.thread.is_alive():
            self.log_file = filename
            
            self.running = True
            
            self.cell.flushInput()
            self.cell.sample()
            self.thread.start()
            self.log.info("Loadcell started")
            
    def pause(self):
        """
        Pauses the loadcell and loadcell thread.
        """
        try:
            self.cell.stop()
        except serial.SerialException:
            pass
            
        self.running = False
        self.thread.join()
        self.log.info("Loadcell paused")

    def stop(self):
        """
        Stops the loadcell and loadcell thread. Saves data to file
        """
        try:
            self.cell.stop()
        except serial.SerialException:
            pass
            
        self.running = False
        self.thread.join()
        self.log.info("Loadcell stopped")
        self.process_data()
        self.raws = []
        
    def loop(self):
        """
        Threading loop
        """
        while(self.running):
            self.getData()

    def getData(self):
        """
        Reads raw loadcell data from serial handle
        """
        raw = ""
        try:
            raw = self.cell.receive()
        except serial.SerialException:
            self.running = False
        else:
            self.raws.append(raw)

    def adcToForce(self, x):
        """
        Converts the adc counts to newtons using precalculated constants
        """
        slope = -1.46
        intercept = 33845.0

        grams = (x - intercept)/slope
        n = grams/1000*9.8
        return n
                
    def process_data(self):
        """
        Parses the loadcell data and save it to self.log_file
        """
        with open(self.log_file, "w") as f:
            f.write("Index\tMicroseconds\tRaw\tNewtons\tAvg\n")
            
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
                else:
                    self.log.warning("Unable to parse loadcell data: {}", self.raws[i])

    

