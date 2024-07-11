import atexit
import logging
import serial
import serial.tools.list_ports
import serial.serialutil

class MKSTeensy(serial.Serial):
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        super().__init__(baudrate=115200, timeout=None)

        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.hwid = config_dict["teensy_hwid"]
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

    def connect(self):
        self.port = self.findUsbPort(self.hwid)
        if self.port is None:
            msg = "MKS Teensy not found!"
            self.log.critical(msg)
            return False
        if self.is_open:
            self.close()
        self.open()
        self.reset_input_buffer()
        self.reset_output_buffer()
        self.connected = True
        self.log.info("Connected to MKS Teensy (%s)", self.port)
        atexit.register(self.disconnect)
        return True
    
    def disconnect(self):
        if self.connected:
            self.close()
            self.connected = False
            self.log.info("Disconnected from MKS Teensy")

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
        return list(self.send("R"))

    def get_all_sensor_status(self):
        return list(self.send("S"))
    
    def get_crane_position(self):
        return self.send("P")
    
    def move_crane(self, mm, relative=False):
        if relative:
            return self.send(f"MR{mm}")
        else:
            return self.send(f"MA{mm}")
        
    def move_crane_top(self):
        return self.send("MT")
        
    def move_crane_bottom(self):
         return self.send("MB")