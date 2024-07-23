import time
import logging

from printer_server.async_file_handler import async_file_hander
from printer_server.hardware_configuration import config_dict, driver_handles
from printer_server.printer_control.print_control import PrintControl, run_in_thread

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class AccelerometerControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.accelerometer = driver_handles.accelerometer

        self.accelerometer_log = str(self.current_job / "logs" / "accelerometer_data.csv")

    def connect_hardware(self):
        accel_connect = self.accelerometer.connect()
        super().connect_hardware()
        if not accel_connect:
            log.error("Accelerometer failed to connect!")
            self.all_hardware_connected = False

    def create_logs(self):
        super().create_logs()

        async_file_hander.write(
            self.accelerometer_log, "system_time,loadcell_time,index,raw_data,newtons\n"
        )
        self.accelerometer.set_log_file(self.accelerometer_log)
