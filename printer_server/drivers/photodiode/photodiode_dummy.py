import logging
from printer_server.logging_handler import dummy_log

class Photodiode_dummy:
    @dummy_log
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        
        self.photodiode = None
        self.connected = None

    @dummy_log  
    def connect(self):
        self.connected = True
    
    @dummy_log
    def disconnect(self):
        self.connected = False
            
    @dummy_log
    def initialize(self):
       pass
   
    @dummy_log
    def set_beam_diameter(self, diameter):
        self.log.debug("Set diameter to %s", diameter)  
        
    @dummy_log
    def set_wavelength(self, length):
        self.log.debug("Set wavelength to %s", length)
    
    @dummy_log
    def set_attenuation_db(self, attenuation):
        self.log.debug("Set attenuation to %s dB", attenuation)
    
    @dummy_log
    def get_power_density(self):      
        return 123.4
       

    