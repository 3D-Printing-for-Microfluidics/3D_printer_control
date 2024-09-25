import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles

spectrometer = driver_handles.spectrometer

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

@socketio.on("spectrometer_capture", namespace="/manual")
def spectrometerCapture(message):
    try:
        auto = int(message["auto"])
        integration = int(message["integration"])
        averages = int(message["averages"])
        if auto == 1:
            integration = None
        integration = spectrometer.set_integration_time(integration)
        spectra = spectrometer.get_spectrum(num_averages=averages)
        socketio.emit("spectrometer_done", {"spectra":spectra, "integration":integration, "averages":averages}, namespace="/manual")
    except Exception as ex:
        log.warn("Spectrometer manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "spectrometer", namespace="/manual")

def spectrometer_load():
    try:
        socketio.emit("spectrometer_load", {
            "integration":spectrometer.config_dict["default_integration_time"], 
            "averages":spectrometer.config_dict["default_number_of_averages"]
        }, namespace="/manual")
    except Exception as ex:
        log.warn("Spectrometer manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "spectrometer", namespace="/manual")
