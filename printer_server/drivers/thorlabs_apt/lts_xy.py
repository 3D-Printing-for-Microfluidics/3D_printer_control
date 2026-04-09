import logging

from printer_server.drivers.generic_drivers import XYStageDriver
from printer_server.drivers.thorlabs_apt.thorlabs_apt import ThorlabsAPT


class LTS_XY(XYStageDriver):
    def __init__(self, config_dict=None, log_level=None):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.apt_controller = ThorlabsAPT(
            config_dict=config_dict, log_level=log_level, driver_name="LTS_XY"
        )
        self.connected = False
        self.initialized = None
        self.config_dict = config_dict
        self.axes_common_names = self.apt_controller.axes_common_names
        self.linked_focus_stage = None
        self.prev_x_position = None
        self.prev_y_position = None

    def setup_log_file(self, filename):
        self.apt_controller.setup_log_file(filename)

    def logging_start(self):
        self.apt_controller.logging_start()

    def logging_stop(self):
        self.apt_controller.logging_stop()

    def connect(self):
        self.connected = self.apt_controller.connect()

    def initialize(self):
        self.apt_controller.initialize()

    def home(self):
        self.apt_controller.home()

    def getDefaultXYSpeed(self, axis=None):
        return self.apt_controller.getDefaultSpeed(axis=axis)

    def getDefaultXYAcceleration(self, axis=None):
        return self.apt_controller.getDefaultAcceleration(axis=axis)

    def getXYPosition(self, axis=None, notify=True):
        if axis == "Y" and self.linked_focus_stage is not None:
            return round(self.apt_controller.getPosition(axis=axis) + self.linked_focus_stage.target_focus, 4)
        else:
            return round(self.apt_controller.getPosition(axis=axis), 4)

    def absMoveXY(
        self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None
    ):
        if axis == "Y" and self.linked_focus_stage is not None:
            mm -= self.linked_focus_stage.target_focus
        if mm < 0 and not self.config_dict["mirroring"][axis]:
            mm = 0
        elif mm > 0 and self.config_dict["mirroring"][axis]:
            mm = 0
        mm = round(mm, 4)
        if axis == "Y":
            self.prev_y_position = mm
        elif axis == "X":
            self.prev_x_position = mm
        self.apt_controller.absMove(mm, speed=speed, acceleration=acceleration, axis=axis)

    def relMoveXY(
        self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None
    ):
        self.absMoveXY(mm=self.getXYPosition(axis=axis) + mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)

    def startXYJog(self, speed=None, acceleration=None, axis=None):
        self.apt_controller.startJog(speed=speed, acceleration=acceleration, axis=axis)

    def stopXYJog(self, axis=None):
        self.apt_controller.stopJog(axis=axis)
        super().stopXYJog(axis=axis)

    def getXYLimits(self, axis=None):
        return self.apt_controller.getLimits(axis=axis)

    def setXYLimits(self, limits=None, axis=None):
        self.apt_controller.setLimits(limits=limits, axis=axis)
