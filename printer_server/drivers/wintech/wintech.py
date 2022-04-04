"""Wintech optical engine controller."""
import time
import logging

from .dlpc900_usb_controller import DLPC900_USB_Controller


class Wintech:
    """Control module for the Wintech optical engine."""

    def __init__(self, log_level=logging.DEBUG):
        self.log_level = log_level
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.dmd_controller = None

    def connect(self):
        """Start the screen thread and connect to the DMD controller."""
        self.dmd_controller = DLPC900_USB_Controller(log_level=self.log_level)
        self.dmd_controller.connect()

    def project(self, exposure_time_ms, repeat=1, led_power=100):
        """Call all of the necessary methods to project an image and
        block until projection is complete. Note that the image must be
        drawn to the virtual screen before this method is called.

        exposure_time_ms: Exposure time (ms).
        repeat: How many times to repeat the exposure. 0 means repeat
            forever.
        led_power: LED power setting (0-100).
        """
        self.log.info(
            "Exposing for %s ms at a power of %s. Repeat %s.",
            exposure_time_ms,
            led_power,
            repeat,
        )
        if 0 > exposure_time_ms > 10000:
            self.log.warning("Exposure time is too high. Using maximum of 10 seconds.")
            exposure_time_ms = 10000
        self.dmd_controller.set_led_power(led_power)
        self.dmd_controller.define_pattern(exposure_time_ms)
        self.dmd_controller.configure_pattern_LUT(repeat=repeat)
        self.dmd_controller.start_sequence()
        time.sleep(exposure_time_ms * 0.001 + 0.1)
