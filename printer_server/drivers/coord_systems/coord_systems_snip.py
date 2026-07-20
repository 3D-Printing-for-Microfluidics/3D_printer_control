from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import config_dict
from printer_server.views.users import socket_require_permissions
import printer_server.views.manual_controls

class Coord_Systems:
    def __init__(self):
        self.coord_system_name = "global"
        self.coord_system = config_dict["coord_systems"][self.coord_system_name]

    def set_coodinate_system(self, coord_system):
        self.coord_system_name = coord_system
        self.coord_system = config_dict["coord_systems"][self.coord_system_name]
        return self.coord_system

    def get_coodinate_system(self):
        return self.coord_system_name, self.coord_system
    
coord_systems_control = Coord_Systems()

@socketio.on("coodinate_system_set_system", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def set_coodinate_system(message):
    """set_coodinate_system -- Sets the variable determining which coordinate system to use"""
    coord_systems_control.set_coodinate_system(message),


def get_coodinate_system(emit=True):
    """Return the current coordinate system."""
    coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
    if emit:
        socketio.emit("get_coodinate_system", coord_system_name, namespace="/manual")
    return coord_system_name, coord_system