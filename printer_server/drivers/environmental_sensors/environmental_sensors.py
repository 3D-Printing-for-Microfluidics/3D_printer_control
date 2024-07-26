import time
import logging
import datetime
from serial import SerialException
from printer_server.threading_wrapper import Thread
from printer_server.drivers.generic_drivers import USBSerial
from printer_server.async_file_handler import async_file_hander

class EnvironmentalSensors(USBSerial):
    """
    Class providing high level control of Environmental Sensor
    """

    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__(vid=config_dict["vendor_id"], pid=config_dict["product_id"], sn=config_dict["serial_number"], baudrate=115200, timeout=1, line_ending='\n', logger=self.log)
        
        self.rest_time = config_dict["measurement_period_ms"]

        self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)
        self.log_file = None
        self.running = False

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
            self.log.info("Environmental sensors started")
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
                    measurement_list = ['iaq','iaqAccuracy','static','co2Equivalent','breathVocEquivalent','rawTemperature','pressure','rawHumidity','gasResistance','stabStatus','runInStatus','temperature','humidity','gasPercentage']
                    file_string = ""
                    file_string += f"{sys_time},"
                    for value in measurement_list:
                        file_string += f"{measurements[value]},"
                    file_string += "\n"

                    async_file_hander.write(
                        self.log_file,
                        file_string,
                    )
                
                time.sleep(self.rest_time/1000)  

            except SerialException:
                self.running = False
            except KeyError:
                pass


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