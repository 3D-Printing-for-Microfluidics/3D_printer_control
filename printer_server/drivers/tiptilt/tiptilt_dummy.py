from printer_server.logging_handler import dummy_log


class TipTilt_dummy:
    @dummy_log
    def __init__(self, *args, **kwargs):
        self.positions = {"tip": 0, "tilt": 0}

    @dummy_log
    def findUsbPort(self, *args, **kwargs):
        pass

    @dummy_log
    def connect(self, *args, **kwargs):
        pass

    @dummy_log
    def send(self, *args, **kwargs):
        pass

    @dummy_log
    def receive(self, *args, **kwargs):
        pass

    @dummy_log
    def initialize(self, *args, **kwargs):
        pass

    @dummy_log
    def home(self, *args, **kwargs):
        self.positions = {"tip": 0, "tilt": 0}

    @dummy_log
    def reset(self, *args, **kwargs):
        pass

    @dummy_log
    def get_position(self, axis):
        return self.positions[axis]

    @dummy_log
    def get_min_position(self, *args, **kwargs):
        pass

    @dummy_log
    def get_max_position(self, *args, **kwargs):
        pass

    @dummy_log
    def get_acceleration(self, *args, **kwargs):
        pass

    @dummy_log
    def set_acceleration(self, *args, **kwargs):
        pass

    @dummy_log
    def get_speed(self, *args, **kwargs):
        pass

    @dummy_log
    def set_speed(self, *args, **kwargs):
        pass

    @dummy_log
    def move_relative(self, axis, distance_um, fast=False):
        self.positions[axis] = self.positions[axis] + distance_um

    @dummy_log
    def move_absolute(self, axis, distance_um, fast=False):
        self.positions[axis] = distance_um

    @dummy_log
    def move(self, axis, distance_um, relative=True, fast=False):
        if relative:
            self.move_relative(axis, distance_um, fast)
        else:
            self.move_absolute(axis, distance_um, fast)
