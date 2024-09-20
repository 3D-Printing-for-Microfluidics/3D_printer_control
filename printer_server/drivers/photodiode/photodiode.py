# Create photodiode instrument 
import time
import pyvisa
import usbtmc
import atexit
import logging
from ThorlabsPM100 import ThorlabsPM100

# first_load = True
# if first_load:
#     first_load = False
#     print(f"PYVISA:")
#     print(f"\t{pyvisa.ResourceManager('@py').list_resources()}")
#     print(f"\t")

class Photodiode:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        # set defaults in init
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        
        self.connected = None
       
        # Variables I may want to change or exist as defaults defined in harware_configuration.json
        self.beamdiameter = config_dict["beam_diameter"]
        self.defaultWavelength = config_dict["default_wavelength"]
        self.attenuation = config_dict["attenuation_db"]
        self.vendor_id = config_dict["vendor_id"]
        self.product_id = config_dict["product_id"]
        self.serial_number = config_dict["serial_number"]

        self.rm = pyvisa.ResourceManager("@py")
       
    def connect(self, shutdown):
        # connect to the photodiode 
        try:
            self.log.info(f"Connecting ThorlabsPM100...")
            self.log.debug("Available PYVISA devices:")
            for r in self.rm.list_resources():
                self.log.debug("\t%s", r)

            self.resource = None
            for r in self.rm.list_resources():
                if f"{self.vendor_id}" in r and f"{self.product_id}" in r and self.serial_number in r:
                    self.resource = r
            self.inst = self.rm.open_resource(self.resource)

            # self.inst = usbtmc.Instrument(self.vendor_id, self.product_id)
            # setattr(self.inst, 'query', self.inst.ask)
            self.power_meter = ThorlabsPM100(inst=self.inst)
            atexit.register(self.disconnect)
            self.connected = True
            self.log.info(f"Connected ThorlabsPM100")
            return True
          
        except Exception as ex:
            self.log.error("Failed to connect to Photodiode (%s)", ex)
            self.connected = False
            return False
            
    def initialize(self):
       # sending cmds to photodiode to set parameters that I want to set initialy
        self.log.info(f"Initializing ThorlabsPM100...")
        self.set_wavelength(self.defaultWavelength)
        self.set_attenuation_db(self.attenuation) 
        self.set_beam_diameter(self.beamdiameter)
        self.power_meter.configure.scalar.pdensity() 
        self.log.info(f"Initialized ThorlabsPM100")

         
    def disconnect(self):
        # disconnects the photodiode     
        if self.connected:
            self.power_meter = None
            self.inst.close()
            self.connected = None
            self.log.info(f"Disconnected to Photodiode")
               
    def set_beam_diameter(self, diameter):
        # set the beam diameter
        # Args: diameter is float 
        if self.power_meter:
            self.power_meter.sense.correction.beamdiameter = diameter
            self.log.debug("Set diameter: %s um",int(self.power_meter.sense.correction.beamdiameter*1000))    
        
    def set_wavelength(self, length):
        # sets the operation wavelength in nm
        # args: length is float 
        if self.power_meter:
            self.power_meter.sense.correction.wavelength = length
            self.log.debug("Set wavelength: %s nm", self.power_meter.sense.correction.wavelength)
            
    def set_attenuation_db(self, attenuation):
        # sets attenuation in dB
        if self.power_meter:
            self.power_meter.sense.correction.loss.input.magnitude = attenuation
            self.log.debug("Set attenuation: %s dB", self.power_meter.sense.correction.loss.input.magnitude)

    def zero(self):
        # zeros the photodiode
        if self.power_meter:
            self.log.debug("Zero point: %s", self.power_meter.sense.correction.collect.zero.magnitude)
            self.power_meter.sense.correction.collect.zero.initiate()
            while bool(self.power_meter.sense.correction.collect.zero.state):
                time.sleep(0.01)
            self.log.debug("Zero point: %s", self.power_meter.sense.correction.collect.zero.magnitude)

    def get_power_density(self):
        # ## also in init 
        # Returns: float, The power density in mW/cm^2.
        if self.power_meter:
            power_density = self.power_meter.read * 1000  # Convert to mW/cm^2
            self.log.info("Irradiance is %s mW/cm^2", power_density)
            return power_density
        return None