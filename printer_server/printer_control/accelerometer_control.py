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
        async_file_hander.write(
            self.accelerometer_log, "system_time,accel_time,index,data\n"
        )
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

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self):
        """Lower the build platform for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            self.accelerometer.start()
            super().planarization_step_1()

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
    
