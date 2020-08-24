import atexit
import serial
import serial.tools.list_ports
import serial.serialutil
import threading
import os

def findUsbPort(hwid):
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if hwid.upper() in p.hwid:
            print("Found '{}' at '{}'".format(p.hwid, p.device))
            return p.device
    return None             # not found

# class LoadCell():
class LoadCellDeviceControl(serial.Serial):

    #def __init__(self, hwid='16c0:0483', verbose=True):
    def __init__(self, hwid='PID=16C0:0483 SER=6256240', verbose=True):
        super().__init__(baudrate=115200, timeout=1)
        # Button parameters
        self.verbose = verbose
        self.hwid = hwid
        self.port = None                # start with no port
        self.status = None              # status to be updated after every send


        atexit.register(self.close)

    def connect(self):
        self.port = findUsbPort(self.hwid)
        if self.port is None:
            raise ValueError('Load cell not found')
        if self.is_open:
            self.close()
        self.open()
        self.flushInput()
        self.flushOutput()
        print("Connected to", self.port)

    def set_gain(self, value):
        """
        Set the gain
        """
        print("gain set to {}", value)
        return self.send('g {}'.format(value)), value

    def set_filter_corner(self, value):
        """
        Set the filter 3d corner
        """
        print("corner set to {}", value)
        return self.send('f {}'.format(value)), value

    def set_sample_period(self, period_us):
        """
        Set the sampling period to period_us (in microseconds)
        """
        print("period set to {}", period_us)
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
        if self.verbose: print('Sent: ' + cmd)
        self.write(bytes(cmd + '\n', encoding='ascii')) # write to serial tx buffer
        response = self.receive()
        if self.verbose: print("Response: ", response)
        return response                                 # return the response to the command

    def receive(self):
        response = b''
        response += self.readline()         # wait for the first line to fill in the rx buffer
        #while self.in_waiting:              # while there is more data in the rx buffer
        #    response += self.readline()     # read next line from rx buffer
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
        #self.thread.start()
        #self.start()
        #self.indexs, self.micros, self.raws = [], [], []
        self.raws = []
        self.cell = LoadCellDeviceControl(verbose=False)

    def start(self):
        
        self.cell.connect()
        self.cell.set_sample_period(1000)
        self.cell.set_gain(100)
        self.cell.set_filter_corner(1000)
        
        self.running = True
        #self.indexs, self.micros, self.raws = [], [], []
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
        #slope = .48
        #intercept = 33247
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
            date_and_time = datetime.now().strftime('%Y_%m_%d__%H_%M_%S')

            # get path to 3D_printer_control
            #self.tcp_log = Path.cwd() / 'logs' / date_and_time
            self.tcp_log = Path.cwd() / 'logs'

            #print(self.tcp_log)
            # create dir if not there
            #try:
            #    os.mkdir(self.tcp_log)
            #except OSError:
            #    print ("Creation of the directory %s failed" % self.tcp_log)
            #else:
            #    print ("Successfully created the directory %s " % self.tcp_log)

            # create logs
            self.tcp_log = str(self.tcp_log / 'load_cell_data_{}.txt'.format(date_and_time))

            #print header
            with open(self.tcp_log, "a") as f:
                f.write("Index\tMicroseconds\tRaw\tNewtons\tAvg\n")

            #sample until running is set to false
            self.cell.flushInput()
            self.cell.sample()
            while(self.running):
                self.getData()
                
            with open(self.tcp_log, "a") as f:
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

    

