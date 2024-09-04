import printer_server.views.manual_controls
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles

keyence = driver_handles.keyence

def read_sensor(index):
    """Returns the readout of the given sensor in um"""
    return keyence.read_sensor(index)
