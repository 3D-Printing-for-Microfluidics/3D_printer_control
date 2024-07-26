# Create photodiode instrument 
import usbtmc
import atexit
import logging
from ThorlabsPM100 import ThorlabsPM100

class Photodiode:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        # set defaults in init
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        
        self.photodiode = None
        self.connected = None
        self.initialized = None
       
        # Variables I may want to change or exist as defaults defined in harware_configuration.json
        
        self.beamdiameter = config_dict["beam_diameter"]
        self.defaultWavelength = config_dict["default_wavelength"]
        self.attenuation = config_dict["attenuation_db"]
        self.vendor_id = config_dict["vendor_id"]
        self.product_id = config_dict["product_id"]
       
    def connect(self):
        # connect to the photodiode 
        try:
            self.inst = usbtmc.Instrument(self.vendor_id, self.product_id)
            setattr(self.inst, 'query', self.inst.ask)
            self.power_meter = ThorlabsPM100(inst=self.inst)
            atexit.register(self.disconnect)
            self.connected = True
            return True
          
        except Exception as e:
            self.log.error(f"Failed to connect to Photodiode: {e}")
            self.connected = False
            return False
            
    def initialize(self):
       # sending cmds to photodiode to set parameters that I want to set initialy
        self.set_wavelength(self.defaultWavelength)
        self.set_attenuation_db(self.attenuation) 
        self.set_beam_diameter(self.beamdiameter)
        self.power_meter.configure.scalar.pdensity() 
        
    #    self.power_meter.sense.correction.wavelength = self.defaultWavelength
    #    self.power_meter.sense.correction.loss.input.magnitude = self.attenuation
        # self.power_meter.sense.correction.beamdiameter = 0.05
        # print(f"Dia: {power_meter.sense.correction.beamdiameter}")

        # # power_meter.sense.average.count = 10
        # power_meter.configure.scalar.power()
        # print(f"{power_meter.read * 1000*1000} uW")

        # power_meter.configure.scalar.pdensity()
        # print(f"{power_meter.read*1000} mW/cm^2")

        # power_meter.configure.scalar.temperature()
        # print(f"T: {[pwer_meter.read} C")
         
    def disconnect(self):
        # disconnects the photodiode     
        if self.connected:
            self.photodiode = None
               
    def set_beam_diameter(self, diameter):
        # set the beam diameter
        # Args: diameter is float 
        if self.power_meter:
            self.power_meter.sense.correction.beamdiameter = diameter
            print(f"Dia: {self.power_meter.sense.correction.beamdiameter}")    
        
    def set_wavelength(self, length):
        # sets the operation wavelength in nm
        # args: length is float 
        if self.power_meter:
            self.power_meter.sense.correction.wavelength = length
            print(f"Wavelength: {self.power_meter.sense.correction.wavelength} nm")
            
    def set_attenuation_db(self, attenuation):
        # sets attenuation in dB
        if self.power_meter:
            self.power_meter.sense.correction.loss.input.magnitude = attenuation
            print(f"Attenuation: {self.power_meter.sense.correction.attenuation} dB")

    def get_power_density(self):
        # ## also in init 
        # Returns: float, The power density in mW/cm^2.
        if self.power_meter:
            power_density = self.power_meter.read * 1000  # Convert to mW/cm^2
            print(f"{power_density} mW/cm^2")
            return power_density
        return None
    # or the following code: 
        # power_meter.confivure.scalar.pdensity()
        # print(f"{power_meter.read*1000} mW/cm^2")
        

"""       
beam diameter never changes
wavelength only changes on the MR1
what changes among printers? attenuation
don't put in shape or profile if there is no code to set it


Potential variables to put in config_dict. Unsure how to change in hardware.
- attenuation
- bandwidth
- resolution
- range dynamic
        
 """      