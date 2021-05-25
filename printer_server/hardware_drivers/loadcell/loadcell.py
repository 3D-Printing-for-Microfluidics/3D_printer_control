import atexit
import serial
import datetime
import serial.tools.list_ports
import serial.serialutil
import threading

import logging
    
class LoadCell(serial.Serial):
    """
    Class providing high level control of loadcell
    """
    def __init__(self, log_level=logging.DEBUG):
        """
        Initializes the loadcell
        """
        super().__init__(baudrate=115200, timeout=1)
        self.port = None                # start with no port
        #self.status = None              # status to be updated after every send
        
        self.raws = []
        self.windowData = []
        self.windowSize = 10
        self.start_time = 0
        self.running = False
        self.source_is_battery = False
        
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.thread = threading.Thread(target=self.loop)

    def set_loadcell_source(self, source):
        self.source_is_battery = source
        
    def get_loadcell_source(self):
        return self.source_is_battery
        
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
        
    def adc_to_force(self, x):
        """
        Converts the adc counts to newtons using precalculated constants
        """
        slope = -1.79
        intercept = 32160

        grams = (x - intercept)/slope
        n = -grams/1000*9.8
        return n
        
    def connect(self, hwid='PID=16C0:0483 SER=5712360', period=1000, filter_corner=240):
        """
        Connects to the loadcell and sets parameters.
        
        Parameters:
            hwid        - device identifier
            period      - sample period of loadcell (in milliseconds)
            corner      - corner frequency of loadcell highpass filter (in Hz)
        """
        self.filter_corner = filter_corner
        self.period = period
        self.hwid = hwid
        
        self.port = self.findUsbPort(self.hwid)
        if self.port is None:
            self.log.critical("Load cell not found")
            raise ValueError('Load cell not found')
        if self.is_open:
            self.close()
        self.open()
        self.flushInput()
        self.flushOutput()
        self.receiveAll()
        self.log.debug("Connected to {}", self.port)
        
        self.log.debug("%s", self.set_sample_period(int(self.period)))
        self.log.debug("%s", self.set_gain(100))
        self.log.debug("%s", self.set_filter_corner(int(self.filter_corner)))
        self.log.info("Connected to loadcell")
        
        atexit.register(self.close)

    def start(self):
        """
        Starts the loadcell collecting data
        """
        if not self.thread.is_alive():
            self.running = True
            
            self.flushInput()
            
            self.log.info("Loadcell started")
            self.start_time = datetime.datetime.now()
            self.loadcell_start()
            self.thread.start()
            
    def set_log_file(self, filename):
        """
        Sets the filepath to save the log to
        
        Parameters:
            filename    - local path and filename (current_job/loadcell_data.txt)
        """
        self.log_file = filename
            
    def pause(self):
        """
        Pauses the loadcell and loadcell thread.
        """
        self.running = False
        self.thread.join()
        self.thread = threading.Thread(target=self.loop)
        
        try:
            self.loadcell_pause()
        except serial.SerialException:
            pass
        self.log.info("Loadcell paused")

    def stop(self, save=True):
        """
        Stops the loadcell and loadcell thread. Saves data to file
        """
        if self.running:
            self.running = False
            self.thread.join()
            self.thread = threading.Thread(target=self.loop)
            
        try:
            self.loadcell_stop()
        except serial.SerialException:
            pass
        self.log.info("Loadcell stopped")
        
        if save:
            self.log.info("Processing loadcell data")
            self.write_to_file()
            self.log.info("Processing finished")
        self.raws = []
        self.windowData = []
        
       
    def get_current_data(self):
        """
        Get current loadcell force
        """
        data = self.process_data(self.windowData, False)
        if len(data) == 0:
            return 0
        else:
            data.reverse()
            return data[0]
        
    def get_current_force(self):
        """
        Get all current loadcell data
        """
        data = self.get_current_data()
        if data == 0:
            return 0
        return data["avg"]
        
    def loop(self):
        """
        Threading loop
        """
        while(self.running):
            raw = ""
            try:
                raw = self.receive()
            except serial.SerialException:
                self.running = False
            else:
                self.raws.append(raw)
                
                if len(self.windowData) >= 10:
                    self.windowData.pop(0)
                self.windowData.append(raw)
                
    def write_to_file(self):
        """
        Parses the loadcell data and save it to self.log_file
        """
        with open(self.log_file, "w") as f:
            f.write("Timestamp\tIndex\tRaw\tNewtons\tAvg\n")
            rows = self.process_data(self.raws, True)
            for row in rows:
                f.write("{}\t{}\t{}\t{}\t{}\n".format(row["time_str"], row["index"], row["raw_data"], row["force"], row["avg"]))

        
    def process_data(self, raw_data, write_to_file):
        """
        Processes raw data to add averaging, force conversion, and timestamps
        
        Returns:
        - 2D array
            [x][0] Timestamp
            [x][1] Datapoint index
            [x][2] Raw Data
            [x][3] Force (in N)
            [x][4] Running Average
        """
        output_array = []
        avg_array = []
        avg_length = 10
        
        length = len(raw_data)
#        last_index = 0
        #for i in range(length - 2):
        for i in range(length):
            splitData = raw_data[i].split(",")
            if(len(splitData) == 3):
                index = splitData[0]
                milliseconds = splitData[1]
                data = splitData[2]

                try:
                    index = int(index)
                    time = self.start_time + datetime.timedelta(milliseconds=float(milliseconds))
                    data = float(data)
                    force = self.adc_to_force(data)
                except ValueError:
                    self.log.debug("Unable to parse loadcell data - cast error")
                    continue
                    
#                if index != last_index + 1:
#                    last_index = index
#                    continue
#                last_index = index
                    
                if len(avg_array) >= avg_length:
                    avg_array.pop(0)
                avg_array.append(force)
                
                avg = 0
                for i in avg_array:
                    avg += i
                avg = avg / len(avg_array)
                
                try:
                    dict = {
                      "timestamp": time.timestamp()*1000,
                      "avg": avg
                    }
                    if write_to_file:
                        dict["time_str"] = time.strftime("%Y-%m-%d %H:%M:%S.%f'")[:-4]
                        dict["index"] = index
                        dict["raw_data"] = data
                        dict["force"] = force
                        
                    output_array.append(dict)
                except OverflowError:
                    self.log.debug("Unable to parse loadcell data - time overflow")
                    pass
            else:
                self.log.debug("Unable to parse loadcell data - corrupt data")
                pass
        return output_array
        
    ########################
    # Teensy serial wrappers
    ########################
    
    def loadcell_start(self):
        """
        Sample at a period of period_us (in microseconds)
        """
        return self.send('b')
        
    def loadcell_pause(self):
        """
        Pause sampling
        """
        return self.send('p')

    def loadcell_stop(self):
        """
        Stop sampling
        """
        return self.send('e')

    def set_gain(self, value):
        """
        Set the gain
        """
        self.log.debug("Gain set to {}", value)
        return self.send('g {}'.format(value)), value

    def set_filter_corner(self, value):
        """
        Set the filter 3d corner
        """
        self.log.debug("Corner set to {}", value)
        return self.send('f {}'.format(value)), value

    def set_sample_period(self, period_us):
        """
        Set the sampling period to period_us (in microseconds)
        """
        self.log.debug("Period set to {}", period_us)
        return self.send('p {}'.format(period_us)), period_us

    def send(self, cmd):
        """
        Sends serial command to the loadcell device
        """
        self.log.debug("Sent: {}", cmd)
        self.write(bytes(cmd + '\n', encoding='ascii')) # write to serial tx buffer
        response = self.receive()
        self.log.debug("Response: {}", response)
        return response                                 # return the response to the command

    def receive(self):
        """
        Sends serial response from the loadcell device
        """
        response = b''
        response += self.readline()         # wait for the first line to fill in the rx buffer
        return response.decode().rstrip()   # return decoded byte response (as string) without traililng newline
        
    def receiveAll(self):
        response = b''
        response += self.readline()         # wait for the first line to fill in the rx buffer
        while self.in_waiting:              # while there is more data in the rx buffer
            response += self.readline()     # read next line from rx buffer
        return response.decode().rstrip()   # return decoded byte response (as string) without traililng newline
