# -*- coding: utf-8 -*-
"""
Visitech and Wintech optical engine control code
=========
"""
import time
import atexit

from ..screen import ScreenThread
from .usb_driver import WintechUSB

class Wintech:
    """ Control module for the Wintech optical engine
    """
    def __init__(self, resolution=(1920, 1080), fullscreen=True, verbose=False):
        self.resolution = resolution
        self.fullscreen = fullscreen
        self.dmd_controller = WintechUSB(verbose=verbose)
        self.screenThread = ScreenThread(self.resolution, self.fullscreen)
        self.ledPower = 0
        atexit.register(self.screenThread.stop)
        atexit.register(self.dmd_controller.stopSequence)
        atexit.register(self.dmd_controller.ledOff)

    # start the screen thread and dmd_controller
    def connect(self, quick=False):
        self.screenThread.start()
        self.dmd_controller.connect(quick)

    def projectMulti(self, images, exposureTimes, ledPowers):
        """Project multiple images with its own exposure time and
        and LED power setting.
        :param list images: a list of image filenames
        :param list exposureTimes: a list of exposure times (ms)
        :param list ledPowers: a list of led power settings
                               (0-1000)
        """
        for image, exposure, ledPower in zip(images, exposureTimes, ledPowers):
            self.project(image, exposure, ledPower)

    def project(self, image, exposure, repeat=1, ledPower=100):
        """Project a image for a period of exposure (ms).
        :param image: an 8-bit grayscale image filename
        :param int exposure: exposure time (ms)
        :param int ledPower: LED power setting (0-100)
        """

        # break exposures larger than 10,000 into a series of shorter exposures
        max_time = 10000
        n = int(exposure // max_time)
        if exposure % max_time != 0:
            exposure = [max_time] * n + [exposure % max_time]
        else:
            exposure = [max_time] * n

        # update LED power if necessary
        if ledPower != self.ledPower:
            self.dmd_controller.setLedPower(ledPower)

        # run each shorter exposure
        for t in exposure:
            self.dmd_controller.definePattern(t)                    # must define pattern, then configure the LUT
            self.dmd_controller.configurePatternLut(repeat=repeat)  # defaults to 1 pattern, repeat once
            self.screenThread.screen.draw(image)                    # draw the image on the virtual screen
            time.sleep(0.1)

            self.dmd_controller.startSequence()                     # send the start command to the DLPC900 controller

            if repeat != 0:                                         # if not repeating forever
                time.sleep(t * .001 + 0.1)                          # wait for the exposure to complete before issuing stop command
                self.dmd_controller.stopSequence()                  # issue stop command to DLPC900

    def clear(self):
        """Clear the projector screen to be black"""
        self.screenThread.screen.clear()
