import atexit
import logging
import numpy as np
import seabreeze.spectrometers as sb

class Spectrometer_dummy:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.connected = None

    def connect(self):
        self.log.debug("Connected")
        self.connected = True
        

    def disconnect(self):
        self.log.debug("Disconnected")
        self.connected = False
        

    def set_integration_time(self, time=None):
        self.log.debug("Set integration time to %s", time)


    def get_integration_limits(self):
        return (1,100)
    

    def get_max_intensity(self):
        return 65535
    

    def get_spectrum(self, num_averages=1):
        return np.array([1,2,3,4,5], [0,0,100,100,0])