from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles

photodiode = driver_handles.photodiode

@socketio.on("read_photodiode_power", namespace="/manual")
def get_photodiode_power(message):
    wavelength = int(message["wavelength"])
    photodiode.set_wavelength(wavelength)
    power = photodiode.get_power_density()
    # or? # photodiode.get_power_density(message)
    socketio.emit("send_photodiode_power", {"power":power, "wavelength":wavelength}, namespace="/manual", broadcast=True)

    
   


