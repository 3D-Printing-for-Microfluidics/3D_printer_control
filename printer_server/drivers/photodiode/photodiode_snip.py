from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles

photodiode = driver_handles.photodiode

@socketio.on("photodiode_get_power", namespace="/manual")
def get_photodiode_power(message, emit=True):
    wavelength = int(message["wavelength"])
    photodiode.set_wavelength(wavelength)
    power = round(photodiode.get_power_density(),2)
    if emit:
        socketio.emit("photodiode_return_power", {"power":power}, namespace="/manual")
    return power

@socketio.on("photodiode_zero", namespace="/manual")
def zero_photodiode():
    photodiode.zero()
    socketio.emit("photodiode_done", namespace="/manual")
