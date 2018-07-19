import serial
import serial.tools.list_ports
import serial.serialutil
import time
import sys

HWID = '1A86:7523'  # this is the product and vendor ID for the knock-off Arduino Uno

class grblConfig(serial.Serial):
    def __init__(self, hwid, verbose=False):
        super().__init__(baudrate=115200, timeout=None)
        self.verbose = verbose
        self.hwid = hwid
        
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

    def send(self, cmd):
        # send the command to grbl
        if self.verbose: print('Sent: ' + cmd)
        response = self.transmit(cmd)
        if self.verbose: print("Response: ", response)
        
        # return the reponse of the first command 
        return response

    def transmit(self,cmd):
        self.write(bytes(cmd + '\r', encoding='ascii')) # write to serial tx buffer 
        return self.receive()                           # wait for response from serial rx buffer
        
    def receive(self):
        response = b''
        response += self.readline()         # wait for the first line to fill in the rx buffer 
        time.sleep(1)
        while self.in_waiting:              # while there is more data in the rx buffer      
            response += self.readline()     # read next line from rx buffer 
        return response.decode().rstrip()   # return decoded byte response (as string)

    def __del__(self):
        try:
            self.close()
        except serial.serialutil.SerialException:
            pass

def helpmsg():
    helpmsg = """
        {0}
        
        This tool reads, sets, and saves grbl configuration parameters. 

        -s [filename]       Save current grbl config to a file
        -w [filename]       Write config specified in file to grbl 

        Examples: 

            Write the settings in file.txt to grbl: 

                python3 {0} -w /path/to/config/file.txt

            Save current grbl settings to file.txt

                python3 {0} -s /path/to/config/file.txt

        The grbl config file is formatted as one setting per line, as 
        output by the grbl command "$$"

        Example config file: 

            $3=1
            $4=1
            $5=1
            $6=1
            $10=1
            $11=1
            $12=1
            $13=1
            $20=1
            $21=1
            $22=1
            $23=1
            $24=1
            $25=1
            $26=1
            $27=1
            $30=1

        Enjoy!
        
        """.format(sys.argv[0])
    return helpmsg

def findUsbPort(hwid):
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
            if 'ttyUSB' in p.name:
                if hwid in p.hwid:
                    print("Found", p.device)
                    return p.device
               
if __name__ == '__main__':
    
    # check command line 
    if len(sys.argv) == 3 and sys.argv[1] == '-s':
        save = True
    elif len(sys.argv) == 3 and sys.argv[1] == '-w':
        save = False
    else: 
        print(helpmsg())
        exit()

    # open connection 
    s = grblConfig(HWID,verbose=False)
    s.connect()

    if save: 
        # perform save function 
        with open(sys.argv[2], 'w') as configFile: 
            print("Saving grbl config to", sys.argv[2])
            configFile.write(s.send("$$").replace('ok', ''))
    else: 
        # write new configuration line by line 
        print("Opening", sys.argv[2], "...")
        with open(sys.argv[2], 'r') as configFile: 
                configuration = configFile.readlines()  # save as array of strings 
        
        print("Writing new settings...")
        for setting in configuration: 
            setting = setting.rstrip()                  # remove trailing characters 
            s.send(setting)
            print(setting)
