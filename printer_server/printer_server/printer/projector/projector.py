# -*- coding: utf-8 -*-
"""
Projector
=========
"""
import time
import atexit

from .projector_screen import ScreenThread
# from .i2c import LightEngineI2C


class Projector:
    def __init__(self, resolution, fullscreen=True):
        self.resolution = resolution
        self.fullscreen = fullscreen
        self.screenThread = None
        # self.i2c = LightEngineI2C()

        # atexit.register(self.i2c.disconnectServer)
        atexit.register(self.screenThread.stop)
        atexit.register(self.stop)

    def connect(self):
        """Create a :py:class:ScreenThread object and run it.
        Also, connect to the I2C.
        """
        self.screenThread = ScreenThread(self.resolution, self.fullscreen)
        self.screenThread.start()
        # self.i2c.connect()

    def start(self):
        """Turn on the LED in projector"""
        # self.i2c.start()

    def stop(self):
        """Turn off the LED in projector"""
        # self.i2c.stop()

    def setLedAmplitude(self, i):
        """Set the projector LED power level.

        :param int i: between 1 and 1000. If it is too low or
                      too high, the LED amplitude will not be
                      changed.
        """
        # if i >= 1 and i <= 1000:
        #     self.i2c.setLedAmplitude(int(i))

    @property
    def ledPower(self):
        # return self.i2c.ledPower
        pass

    def projectMulti(self, images, exposureTimes, ledPowers):
        """Project multiple images with its own expoure time and
        and LED power setting.

        :param list images: a list of image filenames
        :param list exposureTimes: a list of exposure times (ms)
        :param list ledPowers: a list of led power settings
                               (0-1000)
        """
        for im, exposureTime, ledPower in zip(images, exposureTimes, ledPowers):
            self.project(im, exposureTime, ledPower)

    def project(self, image, exposureTime, ledPower):
        """Poject a image for a period of t (ms).

        :param image: an 8-bit grayscale image filename
        :param int exposureTime: exposure time (ms)
        :param int ledPower: LED power setting (0-1000)
        """
        max_time = 10000
        n = int(exposureTime // max_time)
        if exposureTime % max_time != 0:
            exposureTime = [max_time] * n + [exposureTime % max_time]
        else:
            exposureTime = [max_time] * n

        if ledPower != self.ledPower:
            self.setLedAmplitude(ledPower)

        for t in exposureTime:
            self.sendSequence(t)
            self.screenThread.screen.draw(image)
            time.sleep(0.1)
            self.start()
            time.sleep(0.1 + t * 1e-3)
            self.stop()

    # pylint: disable=unused-argument, unused-variable, too-many-arguments, no-self-use
    def sendSequence(self, exposure, repeat=1, bitdepth=7, vsync=1, darktime=0, bitposition=0):
        """Generate and send control sequence

        :param int exposure: exposure time (ms)
        :param int repeat: number of times to repeat pattern sequence
                           0 - repeat forever, (1-4294967296) - repeat
                           n times
        :param int bitdepth: image bit depth. 7 means 8 bits
        :param int vsync: 1 = Wait for VSYNC before displaying the
                          pattern, 0 = Continue running after previous
                          pattern
        :param int darktime: (0-2^24) Dark display time following exposure
        :param int bitposition: see DLPC900 datasheet

        """
        exptime = int(exposure * 1e3)   # convert to us
        sequence = [[exptime, bitdepth, 1, vsync, darktime, bitposition, 0]]
        # self.i2c.parseSendSequence(sequence, repeat)

    def calibrateProject(self, image, ledPower, repeat, exposureTime):
        """Enable continuous projection of an image for
        calibration

        :param image: an 8-bit grayscale image filename
        :param int ledPower: LED power setting (0-1000)
        :param int repeat: 0 repeats forever, 1 repeat
                           once (normal operation)
        :param int exposureTime: exposure time (ms).
        """
        if repeat != 0:
            self.project(image, exposureTime, ledPower)
        else:
            self.setLedAmplitude(ledPower)
            self.sendSequence(exposureTime, repeat)
            self.screenThread.screen.draw(image)
            time.sleep(0.1)
            self.start()

    def clear(self):
        """Clear the projector screen to be black"""
        self.screenThread.screen.clear()

    # def __del__(self):
    #     try:
    #         self.stop()
    #         self.screenThread.stop()
    #         # self.i2c.disconnectServer()
    #     except AttributeError:
    #         pass


if __name__ == '__main__':
    projectorResolution = (2560, 1600)
    p = Projector(projectorResolution)
    p.connect()
    p.calibrateProject("calibrate.png", 100, 0, 1000)
