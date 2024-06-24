import atexit
import logging
import serial
import serial.tools.list_ports
import serial.serialutil

class MKSSolenoids(serial.Serial):
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        super().__init__(baudrate=115200, timeout=None)

        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.hwid = config_dict["solenoids_hwid"]
        self.port = None  # start with no port
        self.connected = False
        self.initialized = None

    def findUsbPort(self, hwid):
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            if hwid.upper() in p.hwid:
                self.log.debug("Found '%s' at '%s'", p.hwid, p.device)
                return p.device
        return None  # not found

    def connect(self, shutdown):
        self.port = self.findUsbPort(self.hwid)
        if self.port is None:
            msg = "MKS Solenoids not found!"
            self.log.critical(msg)
            return False
        if self.is_open:
            self.close()
        self.open()
        self.reset_input_buffer()
        self.reset_output_buffer()
        self.connected = True
        self.log.info("Connected to MKS Solenoids (%s)", self.port)
        atexit.register(self.disconnect)
        return True
    
    def disconnect(self):
        if self.connected:
            self.close()
            self.connected = False
            self.log.info("Disconnected from MKS Solenoids")

    def send(self, cmd, receive=True):
        self.log.debug("Sent: '%s'", cmd)
        self.write(bytes(cmd + "\r", encoding="ascii"))  # write to serial tx buffer
        if receive:
            response = self.receive()
            self.log.debug("Response: '%s'", response)
            return response  # return the response to the command
        return

    def receive(self):
        """
        Sends serial response from the loadcell device
        """
        response = b""
        response += self.readline()  # wait for the first line to fill in the rx buffer
        self.flushInput()
        return (
            response.decode().rstrip()
        )  # return decoded byte response (as string) without traililng newline
            
    def activate_relay(self, relay_num):
        return self.send(f"H{relay_num}")

    def deactivate_relay(self, relay_num):
        return self.send(f"L{relay_num}")

    def get_all_relay_status(self):
        return self.send("R")

    def get_all_switch_status(self):
        return self.send("S")