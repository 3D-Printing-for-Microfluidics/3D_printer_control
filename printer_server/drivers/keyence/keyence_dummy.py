import logging
import json
import atexit
import socket

from printer_server.logging_handler import dummy_log

class Keyence_dummy:
    @dummy_log
    def __init__(
        self,
        config_dict=None,
        log_level=logging.INFO,
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.connected = False
        self.host = config_dict["address"]
        self.port = config_dict["port"]
        
    @dummy_log
    def connect(self, shutdown):
        self.connected = False
        self.log.info(
            "Connected to Keyence sensor"
        )
        self.connected = True
        atexit.register(self.disconnect)
        return True

    @dummy_log
    def disconnect(self):
        if self.connected:
            self.connected = False
            self.log.info("Disconnected from Keyence sensor")


    # @dummy_log
    def send_command(self, message):
        pass

    @dummy_log
    def read_all(self):
        return [0.0, 0.0]

    @dummy_log
    def read_sensor(self, index):
        """Returns the readout of the given sensor in um"""
        return 0.0