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
        self.hwid = config_dict["hwid"]
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
        try:
            self.initialize()
        except serial.serialutil.SerialException:
            msg = "MKS Solenoids failed to connect!"
            self.log.critical(msg)
            if self.is_open:
                self.close()
            return False
        self.log.info("Connected to MKS Solenoids (%s)", self.port)
        atexit.register(self.disconnect)
        return True
    
    def disconnect(self):
        if self.connected:
            self.close()
            self.connected = False
            self.log.info("Disconnected from MKS Solenoids")

    def send(self, cmd):
        self.log.debug("Sent: '%s'", cmd)
        self.write(bytes(cmd + "\r", encoding="ascii"))  # write to serial tx buffer
        response, error = self.receive(cmd)
        self.log.debug("Reply: '%s'", response)
        if error:
            self.log.warning("There was an error! %s", response)
        return response

    def receive(self, cmd):
        buffer = b""  # buffer for incoming serial communication
        message = ""  # response to be returned
        error = False  # indicates an error from the
        while True:
            buffer = self.readline()  # wait for the first line to fill in the rx buffer
            while self.in_waiting:  # while there is more data in the rx buffer
                buffer += self.readline()  # read next line from rx buffer
            decoded_buffer = (
                buffer.decode().rstrip().replace("\r\n", " ")
            )  # decode the byte response (as string) without newlines
            message += decoded_buffer  # build response
            if "Error" in message:
                error = True  # indicate error state
            if "Done" in message:
                message = message.replace(" Done", "")  # strip out done message
                if "G" in cmd:
                    message = float(
                        re.findall(self.r, message)[0]
                    )  # parse out values for getter commands
                return message, error
            
    def activate_relay(self, relay_num):
        pass

    def deactivate_relay(self, relay_num):
        pass

    def get_all_relay_status(self):
        pass

    def get_all_switch_status(self):
        pass