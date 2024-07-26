import logging

from printer_server.async_file_handler import async_file_hander
from printer_server.hardware_configuration.hardware_configuration import  driver_handles
from printer_server.printer_control.print_control import PrintControl

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class AccelerometerControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.accelerometer = driver_handles.accelerometer

        self.accelerometer_log = str(self.current_job / "logs" / "accelerometer_data.csv")

    def create_logs(self):
        super().create_logs()

        async_file_hander.write(
            self.accelerometer_log, "system_time,accel_time,index,data\n"
        )
        self.accelerometer.set_log_file(self.accelerometer_log)

    def connect_hardware(self):
        accel_connect = self.accelerometer.connect(self.shutdown)
        super().connect_hardware()
        if not accel_connect:
            log.error("Accelerometer failed to connect!")
            self.all_hardware_connected = False

    def print_worker(self):
        if self.state != "printing":
            return
        if not self.accelerometer.running:
            self.accelerometer.start()
        super().print_worker()
        if self.printing_paused.is_set():
            self.accelerometer.pause()

    def finish_print(self):
        self.accelerometer.stop()
        self.accelerometer.set_log_file(None)
        super().finish_print()
    
