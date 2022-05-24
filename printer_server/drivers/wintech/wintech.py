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
        self.repeats = 1
        self.exposure_time = 0
        self.led_on = False

    def connect(self):
        """Start the screen thread and connect to the DMD controller."""
        self.dmd_controller = DLPC900_USB_Controller(log_level=self.log_level)
        self.dmd_controller.connect()

    def stop_sequencer(self):
        """
        Turn the sequencer off.
        """
        self.dmd_controller.stop_sequence()

    def setup_exposure(self, exposure_time_ms, led_power=100, repeat=1):
        """
        Setup an exposure.
            t - exposure time in milliseconds
            p - power setting
            r - number of repeats
        """
        self.repeats = repeat
        self.exposure_time = exposure_time_ms
        min_t = 4.046
        max_t = 10000
        self.log.info(
            "Setting up exposure for %s ms at power setting %s. Repeat %s",
            exposure_time_ms,
            led_power,
            repeat,
        )
        if exposure_time_ms == 0:
            return
        elif exposure_time_ms > max_t:
            msg = f"Exposure time {exposure_time_ms} ms is greater than maximum possible exposure time "
            msg += f"of {max_t} ms. Using exposure time of {max_t} ms instead."
            self.log.warning(msg)
            self.exposure_time = max_t
        elif exposure_time_ms < min_t:
            msg = f"Exposure time {exposure_time_ms} ms is less than minimum possible exposure time "
            msg += f"of {min_t} ms. Using exposure time of {min_t} ms instead."
            self.log.warning(msg)
            self.exposure_time = min_t
        self.dmd_controller.set_led_power(led_power)
        self.dmd_controller.define_pattern(self.exposure_time)
        self.dmd_controller.configure_pattern_LUT(repeat=self.repeats)

    def perform_exposure(self):
        """
        Start an exposure.
        """
        self.led_on = True
        if self.exposure_time != 0:
            if self.repeats == 0:
                self.dmd_controller.start_sequence()
            else:
                self.dmd_controller.start_sequence()
                time.sleep(self.exposure_time * 0.001 + 0.1)
                self.led_on = False

    def project(self, exposure_time_ms, led_power=100, repeat=1):
        """Call all of the necessary methods to project an image and
        block until projection is complete. Note that the image must be
        drawn to the virtual screen before this method is called.

        exposure_time_ms: Exposure time (ms).
        led_power: LED power setting (0-100).
        repeat: How many times to repeat the exposure. 0 means repeat
            forever.
        """
        min_t = 4.046
        max_t = 10000
        self.log.info(
            "Exposing for %s ms at a power of %s. Repeat %s.",
            exposure_time_ms,
            led_power,
            repeat,
        )
        self.dmd_controller.set_led_power(led_power)
        if exposure_time_ms > max_t:
            self.log.warning("Exposure time is too high. Using maximum of 10 seconds.")
            exposure_time_ms = max_t
        elif min_t > exposure_time_ms:
            self.log.warning("Exposure time is too low. Using minimum of 4 milliseconds.")
            exposure_time_ms = min_t
        self.led_on = True
        if repeat == 0:
            self.dmd_controller.define_pattern(10000)
            self.dmd_controller.configure_pattern_LUT(repeat=repeat)
            self.dmd_controller.start_sequence()
        else:
            self.dmd_controller.define_pattern(exposure_time_ms)
            self.dmd_controller.configure_pattern_LUT(repeat=repeat)
            self.dmd_controller.start_sequence()
            time.sleep(exposure_time_ms * 0.001 + 0.1)
            self.led_on = False
