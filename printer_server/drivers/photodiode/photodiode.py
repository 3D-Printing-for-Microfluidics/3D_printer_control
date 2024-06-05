# ### Fix this. This code was based on Dallin's code 
# To actually use this do python setup.py install after downloading the package

# print power_meter.read # Read-only property
# print power_meter.sense.average.count # read property
# power_meter.sense.average.count = 10 # write property
# power_meter.system.beeper.immediate() # method


# #### End Notes
# Create photodiode instrument 
import pyvisa
from ThorlabsPM100 import ThorlabsPM100

class Photodiode:
    
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.config_dict = config_dict
        self.photodiode = None
        self.connected = None
        
        # does the stuff that goes in the config dict be things we are configuring or in the wbepage?
        # what explicitly needs to be added
        self.beamdiameter = config_dict["beamdiameter"]
        self.wavelength = config_dict["wavelength"]
        
        rm = pyvisa.ResourceManagement()
    # print(rm.list_resources())
        # ### Make this a variable 
        deviceID = "USBO::0c1313:0c0872::1928351:INSTR"
        inst = rm.open_resource(deviceID)
        power_meter = ThorlabsPM100(inst=inst)

        # print(f"calibration: {power_meter.calibration.string}")
        # ### This needs to be a variable in the json
        power_meter.sense.correction.beamdiameter = 0.05
        print(f"Dia: {power_meter.sense.correction.beamdiameter}")
        # ### This needs to be a dynamic variable in the json
        power_meter.sense.correction.wavelength = 365
        print(f"Wvlen: {power_meter.sense.correction.wavelength}")

        # # power_meter.sense.average.count = 10
        # power_meter.configure.scalar.power()
        # print(f"{power_meter.read * 1000*1000} uW")

        # power_meter.configure.scalar.pdensity()
        # print(f"{power_meter.read*1000} mW/cm^2")

        # power_meter.configure.scalar.temperature()
        # print(f"T: {[pwer_meter.read} C")

   
    def connect(self):
        # connect to the photodiode 
        self.log.debug("Available Photodiode:")
        for s in sb.list_devices():
            self.log.debug("\t%s", s)

        try:
            if self.config_dict.get("serial num", None) and self.config_dict["serial num"] != "":
                self.photodiode = sb.Photodiode.from_serial_number(self.config_dict["serial num"])
            else:
                self.photodiode = sb.Photodiode.from_first_available()
            
            if self.photodiode is None:
                self.connected = False
            else:
                atexit.register(self.disconnect)
                self.connected = True
                
        except Exception as e:
            self.log.error(f"Failed to connect to Photodiode: {e}")
            self.connected = False
    
            
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
            power_meter.sense.correction.wavelength = length
            print(f"Wavelength: {power_meter.sense.correction.wavelength} nm")
            
    #def set_parameter(self):

    def get_power_density(self):
        # ## also in init 
        # Returns: float, The power density in mW/cm^2.
        if self.power_meter:
            self.power_meter.configure.scalar.pdensity()
            power_density = self.power_meter.read * 1000  # Convert to mW/cm^2
            print(f"{power_density} mW/cm^2")
            return power_density
        return None
    # or the following code: 
        # power_meter.confivure.scalar.pdensity()
        # print(f"{power_meter.read*1000} mW/cm^2")
        
# ## Dynamic 
#     Parameter: irradiance ?? 
#     wavelength: dynamic
#     Diameter: 50 mm **dynamic
        
# ## permanately set in config dictionary
#       bandwidth - high
#       attenuation - ...
        
# ## Questions about

#     resolution: high
#     Range: 
#     Shape: circular
#     profile: flat top? 

# Will the device have defaults if I don't put them in the config dictionary? 

    # OLD STUFF 
    def set_integration_time(self, i_time=None):
        
    def get_integration_limits(self):
   
    def get_max_intensity(self):
   
    def get_absolute_max_intensity(self):
    
    def get_spectrum(self, num_averages=1):
        
    
    








