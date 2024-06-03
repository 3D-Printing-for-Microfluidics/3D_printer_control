import atexit
import logging
import serial
import serial.tools.list_ports
import serial.serialutil


class Environmental_sensors(serial.Serial):
    """
    Class providing high level control of Environmental Sensor
    """

    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        super().__init__(baudrate=115200, timeout=1)
        self.port = None  # start with no port
        self.hwid = config_dict["hwid"]
        self.connected = False


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
        return None  # not found

    def connect(self, shutdown):
        self.port = self.findUsbPort(self.hwid)
        if self.port is None:
            msg = "Tip/Tilt stage not found!"
            self.log.critical(msg)
            return False
        if self.is_open:
            self.close()
        self.open()


    def disconnect(self):
        if self.connected:
            self.close()
            self.connected = False
            self.log.info("Disconnected from Environmental Sensor (BME688)")