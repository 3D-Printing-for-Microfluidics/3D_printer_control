"""Wintech optical engine control module."""
import time
import atexit

from ..screen import ScreenThread
from .usb_driver import WintechUSB


class Wintech:
    """Control class for the Wintech optical engine."""

    def __init__(self, resolution=(1920, 1080), fullscreen=True, verbose=False):
        self.resolution = resolution
        self.fullscreen = fullscreen
        self.dmd_controller = WintechUSB(verbose=verbose)
        self.screenThread = ScreenThread(self.resolution, self.fullscreen)
        self.ledPower = 0
        atexit.register(self.screenThread.stop)
        atexit.register(self.dmd_controller.stopSequence)
        atexit.register(self.dmd_controller.ledOff)

    def connect(self, quick=False):
        """Start the screen thread and connect to the DMD controller."""
        self.screenThread.start()
        self.dmd_controller.connect(quick)

    def projectMulti(self, images, exposureTimes, ledPowers):
        """Project multiple images with its own exposure time and
        and LED power setting.

        images: A list of image filenames.
        exposureTimes: A list of exposure times (ms).
        ledPowers: A list of led power settings (0-1000).
        """
        for image, exposure, ledPower in zip(images, exposureTimes, ledPowers):
            self.project(image, exposure, ledPower)

    def project(self, image, exposure, repeat=1, ledPower=100):
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
            self.screenThread.screen.draw(image)
            time.sleep(0.1)
            self.dmd_controller.startSequence()
            if repeat != 0:
                time.sleep(t * 0.001 + 0.1)
                self.dmd_controller.stopSequence()

    def clear(self):
        """Clear the projector screen to black."""
        self.screenThread.screen.clear()
