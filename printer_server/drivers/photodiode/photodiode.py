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
        # set defaults in init
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.config_dict = config_dict
        self.photodiode = None
        self.connected = None
        
        # Leave in only for initial testing
        testState = True
        if testState:
            self.connect()
            self.initialize()
       
        # Variables I may want to change or exist as defaults defined in harware_configuration.json
        
        self.beamdiameter = config_dict["beamdiameter"]
        self.defaultWavelength = config_dict["defaultwavelength"]
        self.attenuation = config_dict["attenuation"]
        self.hwid = config_dict["hwid"]
        
       """
       Values for .json - STARTS LINE 515
       deviceID = "USBO::0c1313:0c0872::1928351:INSTR"
       # ### This needs to be a variable in the json
        power_meter.sense.correction.beamdiameter = 0.05
        print(f"Dia: {power_meter.sense.correction.beamdiameter}")
         
        beam diameter never changes
        wavelength only changes on the MR1
        
        Potential variables to put in config_dict. Unsure how to change in hardware.
        - attenuation
        - bandwidth
        - resolution
        - range dynamic
        
        """       
        # Connect/find the device
        rm = pyvisa.ResourceManagement()
    # print(rm.list_resources())
        # ### Make this a variable 
        
        inst = rm.open_resource(hwid)
        power_meter = ThorlabsPM100(inst=inst)

   
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
            
    def initialize(self):
       # sending cmds to photodiode to set parameters that I want to set initialy
       """ 
         # ### This needs to be a dynamic variable in the json
        power_meter.sense.correction.wavelength = 365
        print(f"Wvlen: {power_meter.sense.correction.wavelength}")
        
        from bp_control
         def initalize_hardware(self):
        bp_pos = self.bp_stage.top_position
        self.bp_thread = self.bp_stage.initialize_and_positionBP(bp_pos)
        super().initalize_hardware()
        if self.bp_thread is not None:
            self.bp_thread.join()
        self.bp_stage.initialized = True
        
        """
        pass
            
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
        
'''
what changes among printers? 
attenuation

'''
# ## permanately set in config dictionary
#       bandwidth - high
#       attenuation - ...
        
# ## Questions about

#     resolution: high
#    ## Don't worry : Range: dynamic? Code that changes this
#     Shape: circular
#     profile: flat top? 
'''
don't put in shape or profile if there is no code ot set it


'''

 # print(f"calibration: {power_meter.calibration.string}")
       
       

        # # power_meter.sense.average.count = 10
        # power_meter.configure.scalar.power()
        # print(f"{power_meter.read * 1000*1000} uW")

        # power_meter.configure.scalar.pdensity()
        # print(f"{power_meter.read*1000} mW/cm^2")

        # power_meter.configure.scalar.temperature()
        # print(f"T: {[pwer_meter.read} C")






