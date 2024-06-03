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
        self.connected = True
        self.log.info("Connected to Environmental Sensor (%s)", self.port)
        atexit.register(self.disconnect)


    def disconnect(self):
        if self.connected:
            self.close()
            self.connected = False
            self.log.info("Disconnected from Environmental Sensor (BME688)")


    ########################
    # Teensy serial wrappers
    ########################
            

    def get_all_measurements(self):
        response = self.send("e")
        return response.split(",")
    
    def get_temperature(self):
        return self.send("t")
    
    def get_humidity(self):
        return self.send("h")

    def get_pressure(self):
        return self.send("p")

    def get_gas(self):
        return self.send("g")

    def get_airQuality(self):
        response = self.send("q")
        return response.split(",")

    def get_voc(self):
        return self.send("v")    



    def send(self, cmd, receive=True):
        """
        Sends serial command to the loadcell device
        """
        self.log.debug("Sent: '%s'", cmd)
        self.write(bytes(cmd + "\n", encoding="ascii"))  # write to serial tx buffer
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
        return (
            response.decode().rstrip()
        )  # return decoded byte response (as string) without traililng newline
