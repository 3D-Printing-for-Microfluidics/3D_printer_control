import logging
import time

class DLPC900_USB_Controller_dummy:
    def __init__(self, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.connected = False
        self.exposure_time = 0
        self.led_power = 0
        self.repeats = 1

    def connect(self, vendor_id, product_id):
        self.log.info(f"Dummy: Connecting to vendor {vendor_id} and product {product_id}")
        self.connected = True
        return self.connected

    def disconnect(self):
        self.log.info("Dummy: Disconnecting")
        self.connected = False

    def initialize(self):
        self.log.info("Dummy: Initializing the DMD controller")

    def stop_sequence(self):
        self.log.info("Dummy: Stopping sequence")

    def set_led_power(self, power):
        self.log.info(f"Dummy: Setting LED power to {power}")
        self.led_power = power

    def define_pattern(self, exposure_time):
        self.log.info(f"Dummy: Defining pattern with exposure time {exposure_time} ms")
        self.exposure_time = exposure_time

    def configure_pattern_LUT(self, repeat=1):
        self.log.info(f"Dummy: Configuring pattern LUT with repeat {repeat}")
        self.repeats = repeat

    def start_sequence(self):
        self.log.info("Dummy: Starting sequence")
        if self.repeats == 0:
            self.log.info("Dummy: Repeating exposure indefinitely")
        else:
            self.log.info(f"Dummy: Exposing for {self.exposure_time} ms {self.repeats} times")
            time.sleep(self.exposure_time * 0.001 * self.repeats)