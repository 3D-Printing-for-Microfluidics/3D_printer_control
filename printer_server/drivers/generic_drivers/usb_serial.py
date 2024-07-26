
import time
import atexit
import serial
import logging
import serial.tools.list_ports

class USBSerial(serial.Serial):
    def __init__(self, vid=None, pid=None, sn=None, baudrate=115200, timeout=None, line_ending='\r', logger=logging.getLogger(__name__)):
        super().__init__(baudrate=baudrate, timeout=timeout)
        self.log = logger
        self.vid = vid
        self.pid = pid
        self.sn = sn
        self.port = None
        self.name = None
        self.connected = None
        self.initialized = None
        self.line_ending = line_ending
    
    def findUsbPort(self, vid, pid, sn=None):
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            self.log.debug(p.hwid)
            self.log.debug(p.vid)
            self.log.debug(p.pid)
            self.log.debug(p.serial_number)
            self.log.debug(p.manufacturer)
            self.log.debug(p.product)
            if p.vid == vid and p.pid == pid:
                if sn is None or sn.upper() in p.serial_number:
                    self.log.debug("Found '%s %s' at '%s'", p.manufacturer, p.product, p.device)
                    return p.device, f"{p.manufacturer} {p.product}"
        return None, None
    
    def connect(self):
        if self.connected is None:
            self.connected = False
            self.port, self.name = self.findUsbPort(self.vid, self.pid, self.sn)
            if self.port is None:
                msg = "Device not found!"
                self.log.critical(msg)
                return False
            if self.is_open:
                self.close()
            self.open()
            self.flush_buffers()
            self.connected = True
            self.log.info("Connected to device (%s)", self.name)
            atexit.register(self.disconnect)
            return True
        else:
            while self.connected is False:
                time.sleep(0.1)
    
    def initialize(self):
        pass
    
    def disconnect(self):
        if self.connected is not None and self.connected:
            self.close()
            self.connected = None
            self.initialized = None
            self.log.info("Disconnected from device (%s)", self.name)

    # line endings \r, \n
    def send(self, cmd, recieve=True):
        try:
            self.write(bytes(cmd + self.line_ending, encoding="ascii"))
            self.log.debug("Sent: '%s'", cmd)
        except serial.SerialException as e:
            msg = "Failed to send message! (%s)", e
            self.log.error(msg)
            return False
        if recieve:
            response = self.receive()
            self.log.debug("Response: '%s'", response)
            return response
        return True

    def receive(self):
        response = b""
        try:
            response += self.readline()
        except serial.SerialException as e:
            msg = "Failed to receive message! (%s)", e
            self.log.error(msg)
            return None
        return (
            response.decode().rstrip()
        )
    
    def write_bytes(self, bytes):
        try:
            self.write(bytes)
            return True
        except serial.SerialException as e:
            msg = "Failed to write bytes! (%s)", e
            self.log.error(msg)
            return False
    
    def read_bytes(self, number_of_bytes):
        try:
            return self.read(number_of_bytes)
        except serial.SerialException as e:
            msg = "Failed to read bytes! (%s)", e
            self.log.error(msg)
            return False
        
    def flush_buffers(self):
        # self.flush()
        self.reset_input_buffer()
        self.reset_output_buffer()