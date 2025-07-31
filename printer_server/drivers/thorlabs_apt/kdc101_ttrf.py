import math

from printer_server.drivers.generic_drivers import (
    FocusStageDriver,
    TTRStageDriver,
)
from printer_server.drivers.thorlabs_apt.thorlabs_apt import ThorlabsAPT


class KDC101_TTRF(FocusStageDriver, TTRStageDriver):
    def __init__(self, config_dict=None, log_level=None):
        self.apt_controller = ThorlabsAPT(
            config_dict=config_dict, log_level=log_level, driver_name="KDC101_TTRF"
        )
        self.mount_len = (
            62.2  # Length between screw and pivot of the kinematic mount in mm
        )

    def mm_to_rad(self, mm):
        """Convert mm to radians based on the mount length."""
        return math.atan(mm / self.mount_len)

    def rad_to_mm(self, rad):
        """Convert radians to mm based on the mount length."""
        return self.mount_len * math.tan(rad)

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

    def getDefaultFocusSpeed(self):
        return self.apt_controller.getDefaultSpeed("Focus")

    def getDefaultFocusAcceleration(self):
        return self.apt_controller.getDefaultAcceleration("Focus")

    def getFocusPosition(self, notify=True):
        return self.apt_controller.getPosition(axis="Focus")

    def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.apt_controller.absMove(
            mm, speed=speed, acceleration=acceleration, axis="Focus"
        )

    def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.apt_controller.relMove(
            mm, speed=speed, acceleration=acceleration, axis="Focus"
        )

    def startFocusJog(self, speed=None, acceleration=None):
        self.apt_controller.startJog(speed=speed, acceleration=acceleration, axis="Focus")

    def stopFocusJog(self):
        self.apt_controller.stopJog(axis="Focus")

    def getFocusLimits(self):
        return self.apt_controller.getLimits(axis="Focus")

    def setFocusLimits(self, limits=None):
        self.apt_controller.setLimits(limits=limits, axis="Focus")

    def getTTRPosition(self, axis=None, notify=True):
        return self.mm_to_rad(self.apt_controller.getPosition(axis=axis))

    def absMoveTTR(self, rad=None, axis=None):
        self.apt_controller.absMove(self.rad_to_mm(rad), axis=axis)

    def relMoveTTR(self, rad=None, axis=None):
        self.apt_controller.relMove(self.rad_to_mm(rad), axis=axis)

    def getTTRLimits(self, axis=None):
        """Get the limits for the TTR stage (in mm)."""
        return self.apt_controller.getLimits(axis=axis)

    def setTTRLimits(self, limits=None, axis=None):
        """Set the limits for the TTR stage (in mm)."""
        self.apt_controller.setLimits(limits=limits, axis=axis)
