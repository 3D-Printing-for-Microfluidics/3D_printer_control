from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles

photodiode = driver_handles.photodiode

@socketio.on("read_photodiode_power", namespace="/manual")
def get_photodiode_power(message):
    photodiode.get_power_density(message)
     
@socketio.on("wavelength_350_405", namespace="/manual")
def set_wavelength(message):
    wavelength = int(message["wavelength"])
    photodiode.set_wavelength(wavelength)
    
   
# in phododiode.py set w, get p, emit p
# Set variable power and double check this works
#end of stuff
socketio.emit("send_photodiode_power", {"power":power, "wavelength":wavelength}, namespace="/manual", broadcast=True)