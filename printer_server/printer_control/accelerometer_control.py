import time
import logging

from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.printer_control.print_control import PrintControl, run_in_thread
from printer_server.hardware_configuration.hardware_configuration import  driver_handles

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class AccelerometerControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.accelerometer = driver_handles.accelerometer
        self.accelerometer_log = str(self.current_job / "logs" / "accelerometer_data.csv")

    def create_logs(self):
        super().create_logs()
        self.accelerometer.set_log_file(self.accelerometer_log)

    def connect_hardware(self):
        accel = Thread(log, name="accel_control_connect_thread", target=self.accelerometer.connect)
        accel.start()
        super().connect_hardware()
        accel.join()
        if not self.accelerometer.connected or accel.exception is not None:
            log.error("Accelerometer failed to connect!")
            self.failed_hardware["Accelerometer"] = self.accelerometer

    def initialize_hardware(self):
        accel = Thread(log, name="accel_control_init_thread", target=self.accelerometer.initialize)
        accel.start()
        super().initialize_hardware()
        accel.join()
        if accel.exception is not None:
            log.error("Accelerometer failed to initialize!")
            self.failed_hardware["Accelerometer"] = self.accelerometer

    def print_worker(self):
        if self.state != "printing":
            return
        if not self.accelerometer.running:
            try:
                self.accelerometer.start()
                time.sleep(0.5)
            except Exception as ex:
                log.warning("Unable to start accelerometer (%s)", ex, exc_info=True)
        super().print_worker()
        if self.printing_paused.is_set():
            try:
                self.accelerometer.pause()
            except Exception as ex:
                log.warning("Unable to pause accelerometer (%s)", ex, exc_info=True)

    def finish_print(self):
        try:
            self.accelerometer.stop()
            time.sleep(0.5)
            self.accelerometer.set_log_file(None)
        except Exception as ex:
            log.warning("Unable to stop accelerometer (%s)", ex, exc_info=True)
        super().finish_print()