import os
from printer_server.settings import Config
from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles

keyence = driver_handles.keyence


def read_sensor(index):
    return keyence.read_all()[index + 1]
