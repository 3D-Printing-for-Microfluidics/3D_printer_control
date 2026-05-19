import logging
from printer_server.logging_handler import dummy_log


class GPIO_dummy:
    @dummy_log
    def __init__(self, log_level=logging.DEBUG, **kwargs):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.film_relay_state = None
        self.wintech_fan_relay_state = None
        self.connected = False

    @dummy_log
    def initialize(self, shutdown):
        self.film_relay_state = False
        self.connected = True

    @dummy_log
    def disconnect(self):
        if self.connected:
            self.connected = False

    @dummy_log
    def film_relay_on(self):
        self.film_relay_state = True

    @dummy_log
    def film_relay_off(self):
        self.film_relay_state = False

    @dummy_log
    def wintech_fan_relay_on(self):
        self.wintech_fan_relay_state = True

    @dummy_log
    def wintech_fan_relay_off(self):
        self.wintech_fan_relay_state = False