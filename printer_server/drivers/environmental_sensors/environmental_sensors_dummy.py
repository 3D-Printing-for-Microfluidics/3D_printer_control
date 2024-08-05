import logging
from printer_server.logging_handler import dummy_log


class EnvironmentalSensors_dummy:
    @dummy_log
    def __init__(self, *args, log_level=logging.DEBUG, **kwargs):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.connected = None

    @dummy_log
    def findUsbPort(self, *args, **kwargs):
        pass

    @dummy_log
    def connect(self, *args, **kwargs):
        self.connected=True

    @dummy_log
    def disconnect(self, *args, **kwargs):
        self.connected=False

    @dummy_log
    def set_log_file(self, *args, **kwargs):
        pass

    @dummy_log
    def start(self, *args, **kwargs):
        pass

    @dummy_log
    def stop(self, *args, **kwargs):
        pass

    @dummy_log
    def loop(self, *args, **kwargs):
        pass


    ########################
    # ESP32 serial wrappers
    ########################
            
    @dummy_log
    def get_all_measurements(self, *args, **kwargs):
        pass

    @dummy_log
    def get_temperature(self, *args, **kwargs):
        pass
    
    @dummy_log
    def get_humidity(self, *args, **kwargs):
        pass

    @dummy_log
    def get_pressure(self, *args, **kwargs):
        pass

    @dummy_log
    def get_gas(self, *args, **kwargs):
        pass

    @dummy_log
    def get_airQuality(self, *args, **kwargs):
        pass

    @dummy_log
    def get_voc(self, *args, **kwargs):
        pass


    @dummy_log
    def send(self, *args, **kwargs):
        pass
    
    @dummy_log
    def receive(self, *args, **kwargs):
        pass