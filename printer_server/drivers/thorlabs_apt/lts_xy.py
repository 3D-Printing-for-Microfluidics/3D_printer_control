from printer_server.drivers.generic_drivers import XYStageDriver
from printer_server.drivers.thorlabs_apt.thorlabs_apt import ThorlabsAPT


class LTS_XY(XYStageDriver):
    def __init__(self, config_dict=None, log_level=None):
        self.apt_controller = ThorlabsAPT(
            config_dict=config_dict, log_level=log_level, driver_name="LTS_XY"
        )

    def setup_log_file(self, filename):
        self.apt_controller.setup_log_file(filename)

    def logging_start(self):
        self.apt_controller.logging_start()

    def logging_stop(self):
        self.apt_controller.logging_stop()

    def connect(self):
        return self.apt_controller.connect()

    def initialize(self):
        self.apt_controller.initialize()

    def home(self):
        self.apt_controller.home()

    def getDefaultXYSpeed(self, axis=None):
        return self.apt_controller.getDefaultSpeed(axis=axis)

    def getDefaultXYAcceleration(self, axis=None):
        return self.apt_controller.getDefaultAcceleration(axis=axis)

    def getXYPosition(self, axis=None, notify=True):
        return self.apt_controller.getPosition(axis=axis)

    def absMoveXY(
        self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None
    ):
        self.apt_controller.absMove(mm, speed=speed, acceleration=acceleration, axis=axis)

    def relMoveXY(
        self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None
    ):
        self.apt_controller.relMove(mm, speed=speed, acceleration=acceleration, axis=axis)

    def startXYJog(self, speed=None, acceleration=None, axis=None):
        self.apt_controller.startJog(speed=speed, acceleration=acceleration, axis=axis)

    def stopXYJog(self, axis=None):
        self.apt_controller.stopJog(axis=axis)

    def getXYLimits(self, axis=None):
        return self.apt_controller.getLimits(axis=axis)

    def setXYLimits(self, limits, axis=None):
        self.apt_controller.setLimits(limits=limits, axis=axis)
