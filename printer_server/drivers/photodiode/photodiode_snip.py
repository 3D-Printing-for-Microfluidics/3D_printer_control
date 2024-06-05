from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles


photodiode = driver_handles.photodiode

@socketio.on("photodiode_capture", namespace="/manual")
def photodiodeCapture(message):
    auto = int(message["auto"])
    #don't have this stuff
    integration = int(message["integration"])
    averages = int(message["averages"])
    if auto == 1:
        integration = None
    integration = photodiode.set_integration_time(integration)
    spectra = photodiode.get_spectrum(num_averages=averages)
    #end of stuff
    socketio.emit("photodiode_done", {"spectra":spectra, "integration":integration, "averages":averages}, namespace="/manual", broadcast=True)