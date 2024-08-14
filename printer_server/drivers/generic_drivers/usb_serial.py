import re
import sys
import time
import atexit
import serial
import logging
import threading
import serial.tools.list_ports

# first_load = True
# if first_load:
#     first_load = False
#     ports = list(serial.tools.list_ports.comports())
#     print("USB:")
#     for p in ports:
#         print(f"\t{p.hwid}")
#         print(f"\t{p.vid}:{p.pid}:{p.serial_number}")
#         print(f"\t{p.manufacturer} {p.product}")
#         print("\t")

class USBSerial(serial.Serial):
    def __init__(self, name, vid=None, pid=None, sn=None, baudrate=115200, timeout=None, line_ending='\r', logger=logging.getLogger(__name__)):
        super().__init__(baudrate=baudrate, timeout=timeout)
        self.log = logger
        self.vid = vid
        self.pid = pid
        self.sn = sn
        self.port = None
        self.name = name
        self.type = None
        self.connected = None
        self.line_ending = line_ending

        self._lock = threading.Lock()
        self.r = re.compile(r"\d*\.?\d*\s*$")
    
    def findUsbPort(self, vid, pid, sn=None):
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            if p.vid == vid and p.pid == pid:
                if sn is None or sn.upper() in p.serial_number:
                    self.log.debug("Found '%s %s' at '%s'", p.manufacturer, p.product, p.device)
                    return p.device, f"{p.manufacturer} {p.product}"
        return None, None
    
    def connect(self, shutdown):
        if self.connected is None:
            self.log.info("Connecting to %s...", self.name)
            self.connected = False
            self.port, self.type = self.findUsbPort(self.vid, self.pid, self.sn)
            if self.port is None:
                self.connected = None
                msg = "Device not found!"
                self.log.critical(msg)
                return False
            if self.is_open:
                self.close()
            self.open()
            self.flush_buffers()
            self.connected = True
            self.shutdown = shutdown
            self.log.info("Connected to %s (%s)", self.name, self.type)
            atexit.register(self.disconnect)
            return True
        else:
            while self.connected is False:
                time.sleep(0.1)
    
    def initialize(self):
        pass
    
    def disconnect(self):
        if self.connected is not None and self.connected:
            self.log.info("Disconnecting from %s...", self.name)
            self.close()
            self.connected = None
            self.log.info("Disconnected from %s", self.name)

    def send(self, cmd, recieve=True):
        with self._lock:
            try:
                self.write(bytes(cmd + self.line_ending, encoding="ascii"))
                self.log.debug("Sent: '%s'", cmd)
            except serial.SerialException as e:
                msg = "Failed to send message! (%s)", e
                # self.log.error(msg)
                # return False
                self.log.critical(msg)
                self.shutdown(is_critical = True)
                sys.exit(msg)
            if recieve:
                response = self.receive()
                return self.parse_message(cmd, response)
            return True

    def receive(self):
        message = ""
        while True:
            response = b""
            try:
                response += self.readline()
            except serial.SerialException as e:
                msg = "Failed to receive message! (%s)", e
                # self.log.error(msg)
                # return False
                self.log.critical(msg)
                self.shutdown(is_critical = True)
                sys.exit(msg)
            response = response.decode().rstrip()
            message += response
            message += " "

            if "Error" in response:
                self.log.warning("Response: '%s'", response)
            else:
                self.log.debug("Response: '%s'", response)

            if not self.multiline or (self.multiline and "Done" in message):
                break
        return message
    
    def parse_message(self, cmd, message):
        if not self.multiline:
            return message
        message = message.replace(" Done", "")  # strip out done message
        if "G" in cmd or cmd.upper() == "B":
            message = float(
                re.findall(self.r, message)[0]
            )  # parse out values for getter commands
        return message
        

    def write_bytes(self, bytes):
        try:
            self.write(bytes)
            return True
        except serial.SerialException as e:
            msg = "Failed to write bytes! (%s)", e
            self.log.critical(msg)
            self.shutdown(is_critical = True)
            sys.exit(msg)
    
    def read_bytes(self, number_of_bytes):
        try:
            return self.read(number_of_bytes)
        except serial.SerialException as e:
            msg = "Failed to read bytes! (%s)", e
            self.log.critical(msg)
            self.shutdown(is_critical = True)
            sys.exit(msg)
        
    def flush_buffers(self):
        # self.flush()
        self.reset_input_buffer()
        self.reset_output_buffer()