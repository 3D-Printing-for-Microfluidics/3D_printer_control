"""Wintech optical engine control module."""
import time
import atexit
import logging

from .usb_driver import WintechUSB


class Wintech:
    """Control class for the Wintech optical engine."""

    def __init__(self, log_level=logging.DEBUG):
        self.log_level = log_level
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.ledPower = 0

    def connect(self, quick=False):
        """Start the screen thread and connect to the DMD controller."""
        self.dmd_controller = WintechUSB(log_level=self.log_level)
        self.dmd_controller.connect(quick)

        atexit.register(self.dmd_controller.stopSequence)
        atexit.register(self.dmd_controller.ledOff)

    def project(self, exposure, repeat=1, ledPower=100):
        """Project an image for a period of exposure (ms). Breaks
        exposure times longer than 10,000 into a series of shorter
        exposures.

        image: An 8-bit grayscale image filename.
        exposure: Exposure time (ms).
        repeat: How many times to repeat the exposure. 0 means repeat
            forever.
        ledPower: LED power setting (0-100).
        """
        max_time = 10000
        n = int(exposure // max_time)
        if exposure % max_time != 0:
            exposure = [max_time] * n + [exposure % max_time]
        else:
            exposure = [max_time] * n
        if ledPower != self.ledPower:
            self.dmd_controller.setLedPower(ledPower)
        for t in exposure:
            self.dmd_controller.definePattern(t)
            self.dmd_controller.configurePatternLut(repeat=repeat)
            time.sleep(0.1)
            self.dmd_controller.startSequence()
            if repeat != 0:
                time.sleep(t * 0.001 + 0.1)
                self.dmd_controller.stopSequence()

    def stop(self):
        """Stop the projector."""
        self.dmd_controller.stopSequence()
