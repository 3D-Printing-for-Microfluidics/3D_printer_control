import time
import logging
from pathlib import Path

from printer_server.settings import Config
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles
from printer_server.printer_control.print_control import PrintControl, PrintingException, run_in_thread
import printer_server.views.home as home

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class PlanarizationControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.motor = driver_handles.planarization
        self.motor_log = str(self.current_job / "logs" / "motor_planarization_data.csv")

    def create_logs(self):
        super().create_logs()
        self.motor.set_log_file(self.motor_log)

    def connect_hardware(self):
        planarization_t = Thread(log, name="planarization_connect_thread", target=self.motor.connect)
        planarization_t.start()
        super().connect_hardware()
        planarization_t.join()
        if not self.motor.connected or planarization_t.exception is not None:
            log.error("Planarization motor failed to connect!")
            self.failed_hardware["Planarization Motor"] = self.motor

    def initialize_hardware(self):
        planarization_t = Thread(log, name="planarization_control_init_thread", target=self.motor.initialize, args=[])
        planarization_t.start()
        super().initialize_hardware()
        planarization_t.join()
        if planarization_t.exception is not None:
            log.error("Planarization Motor failed to initialize!")
            self.failed_hardware["Planarization Motor"] = self.motor

    @run_in_thread("planarized", "Planarization Step 2")
    def planarization_step_2(self):
        """
        After loadcell has reached force (Step 1), we wait a configurable delay,
        then tighten using the motor to the configured torque. Abort on timeout.
        """
        super().planarization_step_2()

        try:
            pconf = config_dict["planarization"]
            delay_s = pconf["tighten_delay_ms"] / 1000.0
            timeout_ms = pconf["motor_timeout_ms"]

            log.info("Waiting %.2f s before tightening...", delay_s)
            time.sleep(delay_s)

            # Start tightening to driver's configured torque target
            self.motor.start("tighten")

            start_time = time.time()
            while self.motor.running:
                if (time.time() - start_time) * 1000.0 > timeout_ms:
                    self.motor.stop()
                    raise PrintingException("Planarization tightening timeout")
                time.sleep(0.05)

            log.info("Motor tightening complete.")
            self.motor.set_log_file(None)

        except Exception as ex:
            log.critical("Planarization motor tightening failed (%s)", ex, exc_info=True)
            self.failed_hardware["Planarization Motor"] = self.motor
            raise PrintingException()

    def finish_print(self):
        """
        After printing completes and platform has been raised by the core pipeline,
        untighten the screw to a *lower* torque target, then stop.
        """
        try:
            pconf = config_dict["planarization"]
            timeout_ms = pconf["motor_timeout_ms"]

            # Choose a lower untighten torque target; prefer explicit config,
            # else default to 20% of tighten target.
            unt_kgmm = float(pconf.get(
                "untighten_torque_kgmm",
                0.20 * float(pconf.get("target_torque_kgmm", 40.0))
            ))
            self.motor.set_torque_target_kgmm(unt_kgmm)

            self.motor.start("untighten")
            start_time = time.time()

            while self.motor.running:
                if (time.time() - start_time) * 1000.0 > timeout_ms:
                    self.motor.stop()
                    raise PrintingException("Planarization untightening timeout")
                time.sleep(0.05)

            log.info("Planarization screw untightened to %.3f kg·mm", unt_kgmm)
            self.motor.set_log_file(None)

            # Restore tighten target for future runs
            tighten_kgmm = float(pconf.get("target_torque_kgmm", 40.0))
            self.motor.set_torque_target_kgmm(tighten_kgmm)

        except Exception as ex:
            log.critical("Unable to untighten planarization screw (%s)", ex, exc_info=True)
            self.failed_hardware["Planarization Motor"] = self.motor
            raise PrintingException()

        super().finish_print()
