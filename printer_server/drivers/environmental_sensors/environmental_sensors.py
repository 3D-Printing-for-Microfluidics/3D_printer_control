import json
import time
import atexit
import logging
import datetime
from printer_server.threading_wrapper import Thread
import serial
import serial.tools.list_ports
import serial.serialutil
from printer_server.async_file_handler import async_file_hander


class EnvironmentalSensors(serial.Serial):
    """
    Class providing high level control of Environmental Sensor
    """

    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        super().__init__(baudrate=115200, timeout=1)
        self.port = None  # start with no port
        self.hwid = config_dict["hwid"]
        self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)
        self.rest_time = config_dict["measurement_period_ms"]
        self.log_file = None
        self.connected = False
        self.running = False


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
            msg = "Environmental Sensor not found!"
            self.log.critical(msg)
            return False
        if self.is_open:
            self.close()
        self.open()
        self.connected = True
        self.log.info("Connected to Environmental Sensor (BME688), posrt: %s", self.port)
        atexit.register(self.disconnect)
        return True


    def disconnect(self):
        if self.connected:
            self.close()
            self.connected = False
            self.log.info("Disconnected from Environmental Sensor (BME688)")

    def set_log_file(self, filename):
        """
        Sets the filepath to save the log to

        Parameters:
            filename    - local path and filename (current_job/environmenal_sensors_data.txt)
        """
        self.log_file = filename

    def start(self):
        """
        Starts the environmental sensor collecting data
        """
        if not self.thread.is_alive():
            self.running = True

            self.flushInput()

            self.log.info("Environmental sensors started")

            file_path = "3D_printer_control/printer_server/hardware_configuration.json"
            with open(file_path, 'r') as file:
                # Load the JSON data from the file
                data = json.load(file)
            
            self.rest_time = data["HR5."]["environmental_sensors"]["measurement_period_ms"]
            
            self.thread.start()

    def stop(self):
        """
        Stops the environmental sensors and thread. Saves data to file
        """

        if self.running:
            self.running = False
            self.thread.join()
            self.thread = Thread(self.log, name="environmental_sensors_loop_thread", target=self.loop)

        self.log.info("Environmental sensors stopped")
        self.start_time = 0

    def loop(self):
        """
        Threading loop
        """
        
        while self.running:
            try:

                if self.log_file is not None:
                    sys_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")


                    measurements = self.get_all_measurements()
                    values = list(measurements.values())
                    file_string = ""
                    file_string += f"{sys_time},"
                    for value in measurements.values():
                        if value == values[-1]:
                            file_string += f"{value}\n"
                        else:
                            file_string += f"{value},"

                    async_file_hander.write(
                        self.log_file,
                        file_string,
                    )
                
                time.sleep(self.rest_time/1000)  

            except serial.SerialException:
                self.running = False


    ########################
    # ESP32 serial wrappers
    ########################
            

    def get_all_measurements(self):
        key = {}
        values = ["iaq", "iaqAccuracy", "static", "co2Equivalent", "breathVocEquivalent",
                   "rawTemperature", "pressure", "rawHumidity", "gasResistance", "stabStatus",
                     "runInStatus", "temperature", "humidity", "gasPercentage"]
        response = self.send("e")
        measurements = response.split(",")

        for value, measurement in zip(values, measurements):
            key[value] = measurement

        return key

    
    def get_temperature(self):
        return self.send("t")
    
    def get_humidity(self):
        return self.send("h")

    def get_pressure(self):
        return self.send("p")

    def get_gas(self):
        return self.send("g")

    def get_airQuality(self):
        key = {}
        values = ["iaq", "iaqAccuracy", "staticIaq", "co2Equivalent", "breathVocEquivalent"]
        response = self.send("q")
        measurements =  response.split(",")
        for value, measurement in zip(values, measurements):
            key[value] = measurement

        return key

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
