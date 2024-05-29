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
rm = pyvisa.ResourceManagement()

# print(rm.list_resources())
# ### Make this a variable 
inst = rm.open_resource('USBO::0c1313:0c0872::1928351:INSTR')
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

power_meter.confivure.scalar.pdensity()
print(f"{power_meter.read*1000} mW/cm^2")

# power_meter.configure.scalar.temperature()
# print(f"T: {[pwer_meter.read} C")