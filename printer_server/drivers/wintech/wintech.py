# -*- coding: utf-8 -*-
"""
Visitech and Wintech optical engine control code
=========
"""
import time
import atexit

from .usb_driver import WintechUSB

class Wintech:
    """ Control module for the Wintech optical engine
    """
    def __init__(self, verbose=False):
        self.dmd_controller = WintechUSB(verbose=verbose)
        self.ledPower = 0
        atexit.register(self.dmd_controller.stopSequence)
        atexit.register(self.dmd_controller.ledOff)

    # start the screen thread and dmd_controller
    def connect(self, quick=False):
        self.dmd_controller.connect(quick)


    def project(self, exposure, repeat=1, ledPower=100):
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
            time.sleep(0.1)

            self.dmd_controller.startSequence()                     # send the start command to the DLPC900 controller

            if repeat != 0:                                         # if not repeating forever
                time.sleep(t * .001 + 0.1)                          # wait for the exposure to complete before issuing stop command
                self.dmd_controller.stopSequence()                  # issue stop command to DLPC900

    def stop(self):
        self.dmd_controller.stopSequence()