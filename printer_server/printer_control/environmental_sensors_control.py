import time
import logging

from printer_server.async_file_handler import async_file_hander
from printer_server.hardware_configuration import config_dict, driver_handles
from printer_server.printer_control.print_control import PrintControl, run_in_thread


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class EnvironmentalSensorsControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.environmental_sensors = driver_handles.environmental_sensors

        # log files
        self.environmental_sensors_log = str(self.current_job / "environmental_sensor_data.csv")

    def create_logs(self):
        super().create_logs()

        async_file_hander.write(
            self.environmental_sensors_log, "iaq,iaqAccuracy,static,co2Equivalent,breathVocEquivalent,rawTemperature,pressure,rawHumidity,gasResistance,stabStatus,runInStatus,temperature,humidity,gasPercentage\n"
        )
        self.environmental_sensors.set_log_file(self.environmental_sensors_log)
        self.environmental_sensors.start() 

    def connect_hardware(self):
        environmental_sensors_ret = self.environmental_sensors.connect()
        super().connect_hardware()
        if not environmental_sensors_ret:
            log.error("environmental Sensor failed to connect!")
            self.all_hardware_connected = False

    def finish_print(self):
        self.environmental_sensors.stop()
        self.environmental_sensors.set_log_file(None)
        super().finish_print()
