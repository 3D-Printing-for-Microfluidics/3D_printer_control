import logging
import printer_server.views.manual_controls
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles

keyence = driver_handles.keyence

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def read_sensors(emit=True):
    """Returns the readout of the given sensor in um"""
    try:
        sensors = list(keyence.config_dict["sensors"].keys())
        ret = {}
        for sensor in sensors:
            ret[sensor] = keyence.read_sensor(sensor)

        if emit:
            socketio.emit("keyence_update", ret, namespace="/manual")
        return ret
    except Exception as ex:
        log.warn("Keyence manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "keyence", namespace="/manual")
        return None
