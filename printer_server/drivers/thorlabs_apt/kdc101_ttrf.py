import math
import logging

from printer_server.drivers.generic_drivers import (
    FocusStageDriver,
    TTRStageDriver,
)
from printer_server.drivers.thorlabs_apt.thorlabs_apt import ThorlabsAPT


class KDC101_TTRF(FocusStageDriver, TTRStageDriver):
    def __init__(self, config_dict=None, log_level=None):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.apt_controller = ThorlabsAPT(
            config_dict=config_dict, log_level=log_level, driver_name="KDC101_TTRF"
        )
        self.mount_len = (
            62.2  # Length between screw and pivot of the kinematic mount in mm
        )
        self.tip_multiplier = 1.44
        self.tilt_multiplier = 2.0
        self.connected = False
        self.initialized = None
        self.config_dict = config_dict
        self.axes_common_names = self.apt_controller.axes_common_names
        self.target_focus = 0.0
        self.linked_y_stage = None
        self.prev_tip_position = None
        self.prev_tilt_position = None
        self.prev_rotate_position = None
        self.prev_focus_position = None

    def mm_to_rad(self, mm, axis):
        """Convert mm to radians (of image NOT mirror rotation) based on the mount length."""
        if mm is None:
            return None
        if axis == "Tip":
            return math.atan(mm / self.mount_len)*self.tip_multiplier
        elif axis == "Tilt":
            return math.atan(mm / self.mount_len)*self.tilt_multiplier
        else:
            self.log.warning("Invalid axis for mm_to_rad (%s)", axis)

    def rad_to_mm(self, rad, axis):
        """Convert radians (of image NOT mirror rotation) to mm based on the mount length."""
        if rad is None:
            return None
        if axis == "Tip":
            return self.mount_len * math.tan(rad/self.tip_multiplier)
        elif axis == "Tilt":
            return self.mount_len * math.tan(rad/self.tilt_multiplier)
        else:
            self.log.warning("Invalid axis for rad_to_mm (%s)", axis)

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

    def getDefaultFocusSpeed(self):
        return self.apt_controller.getDefaultSpeed("Focus")

    def getDefaultFocusAcceleration(self):
        return self.apt_controller.getDefaultAcceleration("Focus")

    def getFocusPosition(self, notify=True):
        return round(self.apt_controller.getPosition(axis="Focus"), 4)

    def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        mm = round(mm, 4)
        self.target_focus = mm
        self.apt_controller.absMove(
            mm, speed=speed, acceleration=acceleration, axis="Focus"
        )
        self.prev_focus_position = mm

    def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        pos = round(self.getFocusPosition() + mm, 4)
        self.target_focus = pos
        self.absMoveFocus(pos, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling)
        if self.prev_focus_position is not None:
            self.prev_focus_position += mm

    def startFocusJog(self, speed=None, acceleration=None):
        self.apt_controller.startJog(speed=speed, acceleration=acceleration, axis="Focus")

    def stopFocusJog(self):
        self.target_focus = self.getFocusPosition()
        self.apt_controller.stopJog(axis="Focus")

    def getFocusLimits(self):
        return self.apt_controller.getLimits(axis="Focus")

    def setFocusLimits(self, limits=None):
        self.apt_controller.setLimits(limits=limits, axis="Focus")

    def getTTRPosition(self, axis=None, notify=True):
        return round(self.mm_to_rad(self.apt_controller.getPosition(axis=axis), axis), 4)

    def absMoveTTR(self, rad=None, axis=None):
        rad = round(rad, 4)
        mm = self.rad_to_mm(rad, axis)
        self.apt_controller.absMove(mm, axis=axis)
        if axis == "Tip":
            self.prev_tip_position = rad
        elif axis == "Tilt":
            self.prev_tilt_position = rad
        elif axis == "Rotate":
            self.prev_rotate_position = rad

    def relMoveTTR(self, rad=None, axis=None):
        rad = round(rad, 4)
        cur = self.getTTRPosition(axis=axis)
        self.absMoveTTR(rad=cur+rad, axis=axis)
        if axis == "Tip" and self.prev_tip_position is not None:
            self.prev_tip_position += rad
        elif axis == "Tilt" and self.prev_tilt_position is not None:
            self.prev_tilt_position += rad
        elif axis == "Rotate" and self.prev_rotate_position is not None:
            self.prev_rotate_position += rad

    def getTTRLimits(self, axis=None):
        """Get the limits for the TTR stage (in mm or mrad)."""
        limits = self.apt_controller.getLimits(axis=axis)
        if axis in ["Tip", "Tilt"]:
            # Convert limits from mm to radians
            limits = [self.mm_to_rad(limits[0], axis), self.mm_to_rad(limits[1], axis)]
        return limits

    def setTTRLimits(self, limits=None, axis=None):
        """Set the limits for the TTR stage (in mm)."""
        # note: We set the limits in mm as that is how the stage is defined. 
        #       The tip/tilt multiplier can mess with it otherwise...
        self.apt_controller.setLimits(limits=limits, axis=axis)
