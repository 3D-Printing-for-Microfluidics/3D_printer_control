import time

import logging
from printer_server.logging_handler import dummy_log

class DLPC900_USB_Controller_dummy:
    @dummy_log
    def __init__(self, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.connected = False
        self.exposure_time = 0
        self.led_power = 0
        self.repeats = 1

    @dummy_log
    def connect(self, vendor_id, product_id):
        self.connected = True
        return self.connected

    @dummy_log
    def disconnect(self):
        self.connected = False

    @dummy_log
    def initialize(self):
        pass

    @dummy_log
    def stop_sequence(self):
        pass

    @dummy_log
    def set_led_power(self, power):
        pass

    @dummy_log
    def define_pattern(self, exposure_time):
        self.exposure_time = exposure_time

    @dummy_log
    def configure_pattern_LUT(self, repeat=1):
        self.repeats = repeat

    @dummy_log
    def start_sequence(self):
        if self.repeats != 0:
            time.sleep(self.exposure_time * 0.001 * self.repeats)