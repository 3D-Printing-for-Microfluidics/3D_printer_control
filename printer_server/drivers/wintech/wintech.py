"""Wintech optical engine controller."""
import time
import logging

from .usb_driver import WintechUSB


class Wintech:
    """Control module for the Wintech optical engine."""

    def __init__(self, log_level=logging.DEBUG):
        self.log_level = log_level
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.led_power = 0
        self.dmd_controller = None

    def connect(self, quick=False):
        """Start the screen thread and connect to the DMD controller."""
        self.dmd_controller = WintechUSB(log_level=self.log_level)
        self.dmd_controller.connect(quick)

    def project(self, exposure_time_ms, repeat=1, led_power=100):
        """Call all of the necessary methods to project an image and
        block until projection is complete. Note that the image must be
        drawn to the virtual screen before this method is called.

        exposure_time_ms: Exposure time (ms).
        repeat: How many times to repeat the exposure. 0 means repeat
            forever.
        led_power: LED power setting (0-100).
        """
        if 0 > exposure_time_ms > 10000:
            self.log.warning("Exposure time is too high. Using maximum of 10 seconds.")
            exposure_time_ms = 10000
        if led_power != self.led_power:
            self.dmd_controller.setLedPower(led_power)
            self.led_power = led_power
        self.dmd_controller.definePattern(exposure_time_ms)
        self.dmd_controller.configurePatternLut(repeat=repeat)
        # time.sleep(0.1)
        self.dmd_controller.startSequence()
        time.sleep(exposure_time_ms * 0.001 + 0.1)
