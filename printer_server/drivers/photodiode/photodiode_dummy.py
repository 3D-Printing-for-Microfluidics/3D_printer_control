import logging

class Photodiode_dummy:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        
        self.photodiode = None
        self.connected = None
           
    def connect(self):
        self.log.debug("Connected")
        self.connected = True
    
    def disconnect(self):
        self.log.debug("Disconnected")
        self.connected = False
            
    def initialize(self):
       self.log.debug("Initialized")  
   
    def set_beam_diameter(self, diameter):
        self.log.debug("Set diameter to %s", diameter)  
        
    def set_wavelength(self, length):
        self.log.debug("Set wavelength to %s", length)
    
    def set_attenuation_db(self, attenuation):
        self.log.debug("Set attenuation to %s dB", attenuation)
    
    def get_power_density(self):      
        return 123.4
       

    