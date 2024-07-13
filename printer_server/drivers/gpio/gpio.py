import atexit
import logging
import gpiod

class GPIO:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.connected = False
        self.fan_relay = False
        self.film_relay = False
        self.chip = gpiod.Chip('gpiochip4')  # Replace 'gpiochip0' with your specific chip if different
        if "fan_pin" in config_dict.keys():
            self.fan_relay_pin = config_dict["fan_pin"]
            self.fan_relay_state = None
            self.fan_relay = True
            self.fan_line = self.chip.get_line(self.fan_relay_pin)
        if "film_pin" in config_dict.keys():
            self.film_relay_pin = config_dict["film_pin"]
            self.film_relay_state = None
            self.film_relay = True
            self.film_line = self.chip.get_line(self.film_relay_pin)

    def initialize(self):
        if self.fan_relay:
            self.fan_line.request(consumer='gpio', type=gpiod.LINE_REQ_DIR_OUT, default_vals=[1])
            self.fan_relay_state = False
        if self.film_relay:
            self.film_line.request(consumer='gpio', type=gpiod.LINE_REQ_DIR_OUT, default_vals=[0])
            self.film_relay_state = False
        self.connected = True
        atexit.register(self.disconnect)
        self.log.info("GPIO initialized")

    def disconnect(self):
        if self.connected:
            if self.fan_relay:
                self.fan_line.release()
            if self.film_relay:
                self.film_line.release()
            self.connected = False

    def fan_relay_on(self):
        self.fan_relay_state = True
        self.fan_line.set_value(0)
        self.log.info("Fan relay on")

    def fan_relay_off(self):
        self.fan_relay_state = False
        self.fan_line.set_value(1)
        self.log.info("Fan relay off")

    def film_relay_on(self):
        self.film_relay_state = True
        self.film_line.set_value(1)
        self.log.info("Film relay on")

    def film_relay_off(self):
        self.film_relay_state = False
        self.film_line.set_value(0)
        self.log.info("Film relay off")
