import time
import atexit
import logging

from .screen import ScreenThread
from .ti_dlpc900_i2c import TI_DLPC900_I2C
from .visitech_led_i2c import Visitech_LED_I2C


class Visitech:
    def __init__(self, resolution, fullscreen=True, verbosity=logging.INFO):
        self.resolution = resolution
        self.fullscreen = fullscreen
        self.max_exp_time = 10000  # max single projection time in ms
        self.verbosity = verbosity
        self.led_driver = Visitech_LED_I2C(verbosity=verbosity)
        self.dmd_driver = TI_DLPC900_I2C(verbosity=verbosity)
        self.screenThread = ScreenThread(self.resolution, self.fullscreen)
        atexit.register(self.disconnect)  # register exit handler

    def log(self, lvl, msg):
        """Log message.

        If no logger is supplied, print the std output.
        """
        try:
            self.logger.log(lvl, msg)
        except AttributeError:
            if lvl >= self.verbosity:
                print(f"{msg}")

    def get_status(self, lvl=logging.INFO):
        self.log(lvl, self.dmd_driver.get_all_status())
        self.log(lvl, self.led_driver.get_all_status())

    def connect(self):
        """Connect to hardware, load default settings and initialize virtual screen."""
        self.screenThread.start()
        self.led_driver.load_defaults()
        self.dmd_driver.load_default_configuration()

    def disconnect(self):
        """Stop the virtual screen"""
        self.screenThread.stop()  # stop screen thread on exit

    def clear_image(self):
        """Blank the virtual screen that provides the image to the Visitech.
        Sets full image to black.
        """
        self.screenThread.screen.clear()

    def split_exposure_time(self, exposure):
        """Split a long exposure time into an array of smaller exposure times."""
        n = int(exposure // self.max_exp_time)
        if exposure % self.max_exp_time != 0:
            exposure = [self.max_exp_time] * n + [exposure % self.max_exp_time]
        else:
            exposure = [self.max_exp_time] * n
        return exposure

    def project(self, image, exposure, power, repeats=1):
        """Call all of the necessary methods to project an image, and block until projection
        is complete.

        For continuous projection, repeat should be set to 0. An exposure time of 33100 us is used
        in this case, providing the minimum blanking of 233 us of the full 33333 us cycle (at 30Hz on HDMI).

        """
        self.log(
            logging.INFO,
            "Exposing {} for {} ms at power {}".format(image, exposure, power),
        )
        self.led_driver.set_amplitude(power)
        self.screenThread.screen.draw(image)
        if repeats == 0:
            self.dmd_driver.set_sequencer_lut_definition(33100)
            self.dmd_driver.set_sequencer_lut_config(repeats=0)
            self.dmd_driver.start_sequencer()
        else:  # normal display is desired
            for t in self.split_exposure_time(exposure):
                self.dmd_driver.set_sequencer_lut_definition(exposure=t * 1000)
                self.dmd_driver.set_sequencer_lut_config(repeats=repeats)
                self.dmd_driver.get_all_status()
                self.dmd_driver.start_sequencer()
                self.dmd_driver.get_all_status()
                # wait until the exposure is complete, plus a little wiggle room
                time.sleep(0.1 + t * 1e-3)
                self.dmd_driver.stop_sequencer()
                self.dmd_driver.get_all_status()

    def projectMulti(self, images, exposureTimes, ledPowers):
        """Project multiple images, each with its own expoure time and
        and LED power setting.
        :param list images: a list of image filenames
        :param list exposureTimes: a list of exposure times (ms)
        :param list ledPowers: a list of led power settings
                            (0-1000)
        """
        for image, expTime, power in zip(images, exposureTimes, ledPowers):
            self.project(image, expTime, power)
