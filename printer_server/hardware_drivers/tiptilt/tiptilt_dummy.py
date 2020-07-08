from printer_server.logging_handler import dummy_log


class TipTilt_dummy:
    @dummy_log
    def __init__(self, *args, **kwargs):
        self.position = [0, 0]

    @dummy_log
    def connect(self, *args, **kwargs):
        pass

    @dummy_log
    def home(self, *args, **kwargs):
        pass

    @dummy_log
    def move(self, axis, distance_um, *args, **kwargs):
        if "relative" in kwargs and kwargs["relative"]:
            self.position[axis == "Tip"] += distance_um
        else:
            self.position[axis == "Tip"] = distance_um

    @dummy_log
    def send(self, *args, **kwargs):
        pass

    @dummy_log
    def transmit(self, *args, **kwargs):
        pass

    @dummy_log
    def receive(self, *args, **kwargs):
        pass

    @dummy_log
    def get_position(self, axis, *args, **kwargs):
        return self.position[axis == "Tip"]
