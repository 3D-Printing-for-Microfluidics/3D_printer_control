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
#     print(f"USB:")
#     for p in ports:
#         print(f"\t{p.hwid}")
#         print(f"\t{p.vid}:{p.pid}:{p.serial_number}")
#         print(f"\t{p.manufacturer} {p.product}")
#         print(f"\t")

class USBSerial(serial.Serial):
    def __init__(self, name, vid=None, pid=None, sn=None, baudrate=115200, timeout=None, line_ending='\r', multiline=False, logger=logging.getLogger(__name__)):
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
        self.multiline = multiline

        self._lock = threading.Lock()
        # self.r = re.compile(r"\d*\.?\d*\s*$")
        self.r = re.compile(r"\d*\.?\d+")
    
    def findUsbPort(self, vid, pid, sn=None):
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            if p.vid == vid and p.pid == pid:
                if sn is None or sn.upper() in p.serial_number:
                    self.log.debug("Found '%s %s' at '%s'", p.manufacturer, p.product, p.device)
                    return p.device, f"{p.manufacturer} {p.product}"
        return None, None
    
    def connect(self):
        if self.connected is None:
            self.log.info("Connecting to %s...", self.name)
            self.connected = False
            self.port, self.type = self.findUsbPort(self.vid, self.pid, self.sn)
            if self.port is None:
                self.connected = None
                msg = "Device not found!"
                self.log.error(msg)
                return False
            if self.is_open:
                self.close()
            self.open()
            self.flush_buffers()
            self.connected = True
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
            try:
                self.close()
            except:
                self.log.info("Unable to disconnect from %s", self.name)
            self.connected = None
            self.log.info("Disconnected from %s", self.name)

    def send(self, cmd, recieve=True, parse_float_at_index=None):
        with self._lock:
            self.write(bytes(cmd + self.line_ending, encoding="ascii"))
            self.log.debug("Sent: '%s'", cmd)
            if recieve:
                response = self.receive()
                return self.parse_message(cmd, response, parse_float_at_index)
            return True

    def receive(self):
        message = ""
        while True:
            response = b""
            response += self.readline()
            response = response.decode().rstrip()
            message += response
            message += "\n"

            if "Error" in response:
                self.log.warning("Response: '%s'", response)
            else:
                self.log.debug("Response: '%s'", response)

            if not self.multiline or (self.multiline and "Done" in message):
                break
        return message
    
    def parse_message(self, cmd, message, parse_float_at_index=None):
        if not self.multiline:
            return message.rstrip()
        message = message.replace("Done", "").rstrip()  # strip out done message
        if parse_float_at_index is not None:
            message = float(
                re.findall(self.r, message)[parse_float_at_index]
            )  # parse out values for getter commands
        return message

    def write_bytes(self, bytes):
        with self._lock:
            self.write(bytes)
            return True
    
    def read_bytes(self, number_of_bytes):
        with self._lock:
            return self.read(number_of_bytes)
        
    def flush_buffers(self):
        with self._lock:
            # self.flush()
            self.reset_input_buffer()
            self.reset_output_buffer()