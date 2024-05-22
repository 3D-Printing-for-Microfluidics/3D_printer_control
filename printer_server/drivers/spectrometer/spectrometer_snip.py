from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles


spectrometer = driver_handles.spectrometer

@socketio.on("spectrometer_capture", namespace="/manual")
def spectrometerCapture(message):
    auto = int(message["auto"])
    integration = int(message["integration"])
    averages = int(message["averages"])
    if auto == 1:
        integration = None
    spectrometer.set_integration_time(integration)
    spectrum = spectrometer.get_spectrum(num_averages=averages)
    socketio.emit("spectrometer_done", spectrum, namespace="/manual", broadcast=True)