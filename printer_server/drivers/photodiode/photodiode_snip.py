import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles

photodiode = driver_handles.photodiode

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

@socketio.on("photodiode_get_power", namespace="/manual")
def get_photodiode_power(message={}, emit=True):
    try:
        wavelength = int(message.get("wavelength", photodiode.defaultWavelength))
        photodiode.set_wavelength(wavelength)
        power = round(photodiode.get_power_density(),2)
        if emit:
            socketio.emit("photodiode_return_power", {"power":power, "wavelength":wavelength}, namespace="/manual")
        return power
    except Exception as ex:
        log.warn("Photodiode manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "photodiode", namespace="/manual")
        return None

@socketio.on("photodiode_zero", namespace="/manual")
def zero_photodiode():
    try:
        photodiode.zero()
        socketio.emit("photodiode_done", namespace="/manual")
    except Exception as ex:
        log.warn("Photodiode manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "photodiode", namespace="/manual")
