import logging
import numpy as np
from printer_server.logging_handler import dummy_log

class Spectrometer_dummy:
    @dummy_log
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.connected = None

    @dummy_log
    def connect(self):
        self.connected = True
        
    @dummy_log
    def disconnect(self):
        self.connected = False
        
    @dummy_log
    def set_integration_time(self, time=None):
        pass

    @dummy_log
    def get_integration_limits(self):
        return (1,100)
    
    @dummy_log
    def get_max_intensity(self):
        return 65535
    
    @dummy_log
    def get_spectrum(self, num_averages=1):
        return np.array([[1,2,3,4,5], [0,0,100,100,0]])