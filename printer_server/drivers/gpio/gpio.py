import atexit
import RPi.GPIO

class GPIO:
    def __init__(self, config_dict):
        self.connected = False
        self.fan_relay = False
        self.film_relay = False
        if "fan_pin" in config_dict.keys():
            self.fan_relay_pin = config_dict["fan_pin"]
            self.fan_relay_state = None
            self.fan_relay = True
        if "film_pin" in config_dict.keys():
            self.film_relay_pin = config_dict["film_pin"]
            self.film_relay_state = None
            self.film_relay = True

    def initialize(self):
        RPi.GPIO.setmode(RPi.GPIO.BOARD)
        if self.fan_relay:
            RPi.GPIO.setup(self.fan_relay_pin, RPi.GPIO.OUT)
            self.fan_relay_state = False
            RPi.GPIO.output(self.fan_relay_pin, RPi.GPIO.HIGH)
        if self.film_relay:
            RPi.GPIO.setup(self.film_relay_pin, RPi.GPIO.OUT)
            self.film_relay_state = False
            RPi.GPIO.output(self.film_relay_pin, RPi.GPIO.LOW)
        self.connected = True
        atexit.register(self.disconnect)

    def disconnect(self):
        if self.connected:
            RPi.GPIO.cleanup()
            self.connected = False

    def fan_relay_on(self):
        self.fan_relay_state = True
        RPi.GPIO.output(self.fan_relay_pin, RPi.GPIO.LOW)

    def fan_relay_off(self):
        self.fan_relay_state = False
        RPi.GPIO.output(self.fan_relay_pin, RPi.GPIO.HIGH)

    def film_relay_on(self):
        self.film_relay_state = True
        RPi.GPIO.output(self.film_relay_pin, RPi.GPIO.HIGH)

    def film_relay_off(self):
        self.film_relay_state = False
        RPi.GPIO.output(self.film_relay_pin, RPi.GPIO.LOW)
