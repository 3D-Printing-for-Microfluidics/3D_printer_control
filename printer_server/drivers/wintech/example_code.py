"""A test script for the new Wintech driver.

This should be placed in the top level `3D_printer_control` directory
for the imports to work properly.
"""

import sys
import time
import logging
import random

from printer_server.drivers.screen import ScreenThread
from printer_server.drivers.wintech import Wintech


class LoggingNameFilter(logging.Filter):
    """Strip out only the last part of a name to use with a logger.

    You can also import this class if you don't mind importing the whole
    flask framework to get it with:
    `from printer_server.logging_handler import LoggingNameFilter`
    """

    def filter(self, record):
        record.shortname = record.name.rsplit(".", 1)[-1]
        return True


# Example of how to set up loggers to get log data
fmt = "%(asctime)s.%(msecs)03d [%(levelname)-5.5s]  %(shortname)-18s  %(message)s  "
console_handler = logging.StreamHandler(sys.stdout)
console_handler.addFilter(LoggingNameFilter())
console_handler.setFormatter(logging.Formatter(fmt, "%Y-%m-%d %H:%M:%S"))

root_logger = logging.getLogger()
root_logger.addHandler(console_handler)
root_logger.setLevel(logging.INFO)

log = logging.getLogger(__name__)

# Exammple of how to set up the virtual screen
s = ScreenThread(
    config_dict={
        "light_engines": ["visitech, wintech"],
        "visitech": {
            "leds_nm": [
                365
            ],
            "resolution": [
                1920,
                1080
            ]
        },
        "wintech": {
            "leds_nm": [
                405,
                365
            ],
            "resolution": [
                2560,
                1600
            ]
        }
    },
    log_level=logging.INFO,
)

s.start()
time.sleep(1)  # the screen setup needs a little time to get ready

# Example of how to instantiate the Wintech class
log.info("Setting up Wintech...")
p = Wintech(log_level=logging.INFO)
p.connect()

# Example of how to call functions directly from the controller
p.dmd_controller.get_firmware_version()
p.dmd_controller.get_hardware_configuration_and_firmware_tag()

# Example of how to draw images to Visitech and Wintech virtual screens
s.draw(light_engine="wintech", img_path="printer_server/drivers/wintech/images/1.png")
# s.draw(light_engine="wintech", img_path="printer_server/drivers/wintech/images/white.png")
s.draw(light_engine="visitech", img_path="printer_server/drivers/visitech/images/visitech_1.png")
# s.draw(light_engine="visitech", img_path="printer_server/drivers/visitech/images/white.png")

# Some test code to run a number of projections and report some class data
num_tests = 10
print(f"Exposures using project: {num_tests}")
for _ in range(num_tests):
    p.project(random.randint(5, 1000), led_power=30)
print(f"Exposures using setup/perform_exposure: {num_tests}")
for _ in range(num_tests):
    p.setup_exposure(random.randint(5, 1000), led_power=30)
    p.perform_exposure()
print(f"Exposures using project (repeating): {num_tests}")
for _ in range(num_tests):
    p.project(1000, led_power=30, repeat=0)
    time.sleep(random.randint(500, 3000) / 1000)
    p.stop_sequencer()
print(f"Exposures using setup/perform_exposure (repeating): {num_tests}")
for _ in range(num_tests):
    p.setup_exposure(1000, led_power=30, repeat=0)
    p.perform_exposure()
    time.sleep(random.randint(500, 3000) / 1000)
    p.stop_sequencer()
print(f"Number of images projected: {num_tests}")
print(f"Number of DLPC900 transactions: {p.dmd_controller.transaction_counter}")
print(f"Number of HID writes: {p.dmd_controller.usb_io_counter}")

# An example of how to trigger an error with an invalid command (This
# accesses a protected member and is bad practice, it is used here only
# to illustrate an error)
p.dmd_controller._DLPC900_command("r", 0xBEEF)
