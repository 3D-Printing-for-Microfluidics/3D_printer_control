from printer_server.hardware_configuration import config_dict

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

    def get_all_coodinate_system(self):
        return config_dict["coord_systems"]