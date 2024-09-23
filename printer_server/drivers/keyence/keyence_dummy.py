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
        self.config_dict = config_dict
        
    @dummy_log
    def connect(self):
        self.connected = False
        self.connected = True
        atexit.register(self.disconnect)
        return True

    @dummy_log
    def disconnect(self):
        if self.connected:
            self.connected = False

    # @dummy_log
    def send_command(self, message):
        pass

    @dummy_log
    def read_all(self):
        return [0.0, 0.0]
    
    @dummy_log
    def read_sensor_at_index(self, index):
        return 0.0

    @dummy_log
    def read_sensor(self, sensor):
        """Returns the readout of the given sensor in um"""
        return 0.0