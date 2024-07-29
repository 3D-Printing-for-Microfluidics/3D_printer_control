import re
import atexit
import logging
from printer_server.logging_handler import dummy_log

def get_axis_index(axis):
    axis = axis.lower()
    return {"tip": 1, "tilt": 2}.get(axis, 0)

class TipTilt_dummy:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.port = None
        self.connected = False
        self.r = re.compile(r"\d*\.?\d*$")
        self.initialized = None

    @dummy_log
    def connect(self, shutdown):
        self.port = "dummyPort"
        if self.port is None:
            msg = "Tip/Tilt stage not found!"
            self.log.critical(msg)
            return False
        self.connected = True
        self.initialize()
        atexit.register(self.disconnect)
        self.log.info("Connected to tip/tilt stage (%s)", self.port)
        return True

    @dummy_log
    def disconnect(self):
        if self.connected:
            self.connected = False
            self.log.info("Disconnected from Tip/tilt stage")

    # @dummy_log
    def send(self, cmd):
        self.log.debug("Sent: '%s'", cmd)
        response = "Done" if "G" not in cmd else 0.0  # Dummy response
        error = False
        return response, error

    # @dummy_log
    def receive(self, cmd):
        message = "Done"
        error = False
        return message, error

    @dummy_log
    def initialize(self):
        return self.send("IN0")

    @dummy_log
    def home(self):
        return self.send("HM0")

    @dummy_log
    def reset(self):
        return self.send("RS0")

    @dummy_log
    def get_position(self, axis):
        return self.send("GP{}".format(get_axis_index(axis)))[0]

    # @dummy_log
    def get_min_position(self, axis):
        return self.send("GL{}".format(get_axis_index(axis)))[0]

    # @dummy_log
    def get_max_position(self, axis):
        return self.send("GU{}".format(get_axis_index(axis)))[0]

    # @dummy_log
    def get_acceleration(self, axis):
        return self.send("GA{}".format(get_axis_index(axis)))[0]

    # @dummy_log
    def set_acceleration(self, axis, acceleration):
        return self.send("SA{} {}".format(get_axis_index(axis), acceleration))

    # @dummy_log
    def get_speed(self, axis):
        return self.send("GV{}".format(get_axis_index(axis)))[0]

    # @dummy_log
    def set_speed(self, axis, speed):
        return self.send("SV{} {}".format(get_axis_index(axis), speed))

    @dummy_log
    def move_relative(self, axis, distance_um, fast=False):
        if fast:
            return self.send("Mr{} {}".format(get_axis_index(axis), distance_um))
        return self.send("MR{} {}".format(get_axis_index(axis), distance_um))

    @dummy_log
    def move_absolute(self, axis, distance_um, fast=False):
        if fast:
            return self.send("Ma{} {}".format(get_axis_index(axis), distance_um))
        return self.send("MA{} {}".format(get_axis_index(axis), distance_um))

    @dummy_log
    def move(self, axis, distance_um, relative=True, fast=False):
        if relative:
            self.move_relative(axis, distance_um, fast)
        else:
            self.move_absolute(axis, distance_um, fast)


if __name__ == "__main__":
    t = TipTilt_dummy()
    t.connect(exit)
    print(t.get_position("tip"))
    print(t.get_position("tilt"))