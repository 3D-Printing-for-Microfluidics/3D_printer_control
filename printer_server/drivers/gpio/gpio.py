import atexit
import RPi.GPIO


class GPIO:
    def __init__(self):
        self.film_relay_pin = 7

    def initialize(self):
        RPi.GPIO.setmode(RPi.GPIO.BOARD)
        RPi.GPIO.setup(self.film_relay_pin, RPi.GPIO.OUT)
        RPi.GPIO.output(self.film_relay_pin, RPi.GPIO.LOW)
        atexit.register(RPi.GPIO.cleanup)

    def film_relay_on(self):
        RPi.GPIO.output(self.film_relay_pin, RPi.GPIO.HIGH)

    def film_relay_off(self):
        RPi.GPIO.output(self.film_relay_pin, RPi.GPIO.LOW)
