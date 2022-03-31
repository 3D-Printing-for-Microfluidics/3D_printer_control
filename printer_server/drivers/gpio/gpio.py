import atexit
import RPi.GPIO


class GPIO:
    def __init__(self):
        self.film_relay_pin = 7
        self.film_relay_state = None

    def initialize(self):
        RPi.GPIO.setmode(RPi.GPIO.BOARD)
        RPi.GPIO.setup(self.film_relay_pin, RPi.GPIO.OUT)
        self.film_relay_state = False
        RPi.GPIO.output(self.film_relay_pin, RPi.GPIO.LOW)
        atexit.register(RPi.GPIO.cleanup)

    def film_relay_on(self):
        self.film_relay_state = True
        RPi.GPIO.output(self.film_relay_pin, RPi.GPIO.HIGH)

    def film_relay_off(self):
        self.film_relay_state = False
        RPi.GPIO.output(self.film_relay_pin, RPi.GPIO.LOW)
