from printer_server.extensions import socketio
from printer_server.hardware_configuration import config_dict


class Coord_Systems:
    def __init__(self):
        self.coord_system_name = "global"
        self.coord_system = config_dict["coord_systems"][self.coord_system_name]

    def save_coodinate_system(self, coord_system):
        self.coord_system_name = coord_system
        self.coord_system = config_dict["coord_systems"][self.coord_system_name]
        return self.coord_system

    def get_coodinate_system(self):
        return self.coord_system_name, self.coord_system


coordinate_system = Coord_Systems()


@socketio.on("save_coodinate_system", namespace="/manual")
def save_coodinate_system(message):
    """set_coodinate_system -- Sets the variable determining which coordinate system to use"""
    coordinate_system.save_coodinate_system(message),


def get_coodinate_system(emit=True):
    """Return the current coordinate system."""
    coord_system_name, coord_system = coordinate_system.get_coodinate_system()
    return coord_system_name, coord_system
