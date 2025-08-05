# Raspberry Pi driver for Teensy-based planarization motor
# Protocol (line-based, '\n'-terminated):
#   "t" / "u"          : start tighten / untighten
#   "e"                : stop
#   "s <kgmm>"         : set torque target (kg·mm)
# Telemetry while running:
#   "torque <kgmm>"    : current (filtered) torque reading
#   "start" | "stop" | "done" | "timeout"

import time
import logging
from serial import SerialException
from printer_server.threading_wrapper import Thread
from printer_server.drivers.generic_drivers import USBSerial
from printer_server.async_file_handler import async_file_hander
from printer_server.hardware_configuration.hardware_configuration import config_dict


class Planarization(USBSerial):
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__(
            "Planarization",
            vid=config_dict["vendor_id"],
            pid=config_dict["product_id"],
            sn=config_dict["serial_number"],
            baudrate=config_dict["baudrate"],
            timeout=0.1,
            line_ending="\n",
            multiline=True,
            logger=self.log,
        )

        self.config_dict = config_dict
        self.running = False
        self.thread = Thread(self.log, name="planarization_loop_thread", target=self.loop)
        self.log_file = None

        # Torque targets in kg·mm (preferred)
        pconf = config_dict.get("planarization", {})
        self.torque_target_kgmm = float(pconf.get("target_torque_kgmm", 40.0))

    # ---------- public API ----------

    def start(self, direction: str = "tighten", torque_kgmm: float | None = None):
        """
        Start motor operation. If torque_kgmm is given, set it before motion.
        direction: "tighten" | "untighten"
        """
        if not self.thread.is_alive():
            if torque_kgmm is None:
                torque_kgmm = self.torque_target_kgmm
            self.set_torque_target_kgmm(torque_kgmm)

            self.running = True
            cmd = "t" if direction == "tighten" else "u"
            self.send(cmd, recieve=False)
            time.sleep(0.1)
            self.thread.start()

    def stop(self):
        """Stop motor and the receiver thread."""
        if self.running:
            self.running = False
            self.thread.join()
            self.thread = Thread(self.log, name="planarization_loop_thread", target=self.loop)
            self.send("e", recieve=False)

    def set_log_file(self, filename: str | None):
        """
        Log torque readings to CSV if filename is provided.
        CSV header: system_time,torque_kgmm
        """
        self.log_file = filename
        if self.log_file:
            async_file_hander.write(self.log_file, "system_time,torque_kgmm\n")

    def set_torque_target_kgmm(self, kgmm: float):
        """Send torque target (kg·mm) to Teensy."""
        if kgmm < 0:
            self.log.warning("Invalid torque (kg·mm) target: %s", kgmm)
            return
        self.torque_target_kgmm = float(kgmm)
        self.send(f"s {self.torque_target_kgmm:.3f}", recieve=False)
        self.log.info("Set torque target to %.3f kg·mm", self.torque_target_kgmm)

    # ---------- background receive loop ----------

    def loop(self):
        """
        Receive lines from Teensy while running.
        Expected lines:
          - 'torque <value>'
          - 'done' / 'timeout' / 'start' / 'stop'
        """
        try:
            while self.running:
                line = self.readline()
                if not line:
                    continue
                line = line.strip()

                if line.startswith("torque "):
                    try:
                        val = float(line.split(" ", 1)[1])
                        if self.log_file:
                            async_file_hander.write(self.log_file, f"{time.time()},{val:.3f}\n")
                    except ValueError:
                        self.log.debug("Parse error for torque line: %s", line)
                        continue

                elif "done" in line or "timeout" in line:
                    # Teensy indicates motion completed or timed out
                    self.running = False
                    self.log.info("Planarization motor reported: %s", line)
                    break

                # Optional: log starts/stops for debugging
                elif line in ("start", "stop"):
                    self.log.debug("Motor: %s", line)

        except SerialException as ex:
            self.log.warning("Planarization serial failed (%s)", ex)
            self.running = False
