import time
import logging

from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles
from printer_server.printer_control.print_control import PrintControl, run_in_thread


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class EnvironmentalSensorsControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.environmental_sensors = driver_handles.environmental_sensors

        # log files
        self.environmental_sensors_log = str(self.current_job / "logs" / "environmental_sensor_data.csv")

    def create_logs(self):
        super().create_logs()

        async_file_hander.write(
            self.environmental_sensors_log, "time,iaq,iaqAccuracy,static,co2Equivalent,breathVocEquivalent,rawTemperature,pressure,rawHumidity,gasResistance,stabStatus,runInStatus,temperature,humidity,gasPercentage\n"
        )
        try:
            self.environmental_sensors.set_log_file(self.environmental_sensors_log)
            self.environmental_sensors.start() 
        except Exception as ex:
            log.warning("Unable to start environmental sensors (%s)", ex, exc_info=True)

    def connect_hardware(self):
        self.env_thread = Thread(log, name="env_control_connect_thread", target=self.environmental_sensors.connect)
        self.env_thread.start()
        super().connect_hardware()
        self.env_thread.join()
        if not self.environmental_sensors.connected or self.env_thread.exception is not None:
            log.error("Environmental sensors failed to connect!")
            self.failed_hardware["Environmental Sensor"] = self.environmental_sensors

    def finish_print(self):
        try:
            self.environmental_sensors.stop()
            self.environmental_sensors.set_log_file(None)
        except Exception as ex:
            log.warning("Unable to stop environmental sensors (%s)", ex, exc_info=True)
        super().finish_print()
