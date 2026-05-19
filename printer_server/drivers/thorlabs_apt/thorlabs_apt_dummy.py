import logging
from printer_server.logging_handler import dummy_log


class ThorlabsAPT_dummy:
    @dummy_log
    def __init__(
        self,
        config_dict=None,
        log_level=logging.DEBUG,
        driver_name="ThorlabsAPT_dummy",
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.config_dict = config_dict or {}
        self.driver_name = driver_name

        self.default_axis = self.config_dict.get("default_axis")
        self.axes = self.config_dict.get("axes", [])
        self.axes_common_names = self.config_dict.get("axes_common_names", [])
        self.max_travel_mm = self.config_dict.get("axes_travel", {})
        self.default_speed = self.config_dict.get("axes_speed", {})
        self.default_acceleration = self.config_dict.get("axes_acceleration", {})
        self.mirroring = self.config_dict.get("mirroring", {})
        self.limits = self.config_dict.get("limits", {})

        self.connected = None
        self.initialized = None
        self.homed = None

        self.axes_homed = {}
        self.current_position = {}
        self.speed = {}
        self.acceleration = {}
        self.jogging = {}
        self.pre_jog_speed = {}
        self.pre_jog_acceleration = {}
        self.moving_dir = {}
        for axis in self.axes:
            self.axes_homed[axis] = False
            self.current_position[axis] = 0.0
            self.speed[axis] = 0.0
            self.acceleration[axis] = 0.0
            self.jogging[axis] = False
            self.pre_jog_speed[axis] = 0.0
            self.pre_jog_acceleration[axis] = 0.0
            self.moving_dir[axis] = None

        self.logging_running = False
        self.movement_log = None

    def getCommonName(self, axis):
        if axis is None:
            axis = self.default_axis
        for i in range(len(self.axes)):
            if axis in (self.axes[i], self.axes_common_names[i]):
                return self.axes_common_names[i]
            if axis.upper() in (self.axes[i], self.axes_common_names[i]):
                return self.axes_common_names[i]
            if axis.lower() in (self.axes[i], self.axes_common_names[i]):
                return self.axes_common_names[i]
        raise ValueError("Invalid axis supplied")

    def convertAxis(self, axis=None):
        if axis is None:
            axis = self.default_axis
        for i in range(len(self.axes)):
            if axis in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
            if axis.upper() in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
            if axis.lower() in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
        raise ValueError("Invalid axis supplied")

    def getDefaultSpeed(self, axis=None):
        a = self.convertAxis(axis)
        return self.default_speed.get(a, 0.0)

    def getDefaultAcceleration(self, axis=None):
        a = self.convertAxis(axis)
        return self.default_acceleration.get(a, 0.0)

    @dummy_log
    def connect(self):
        self.connected = True
        return True

    @dummy_log
    def disconnect(self):
        self.connected = False
        self.initialized = None

    @dummy_log
    def initialize(self):
        self.initialized = True

    @dummy_log
    def home(self):
        for axis in self.axes:
            self.axes_homed[axis] = True
            self.current_position[axis] = 0.0
        self.homed = True

    def getPosition(self, axis=None, notify=True):
        a = self.convertAxis(axis)
        pos = self.current_position[a]
        if self.mirroring.get(a):
            return float(-pos)
        return float(pos)

    def getAcceleration(self, axis=None):
        a = self.convertAxis(axis)
        return self.acceleration[a]

    def setAcceleration(self, acceleration, axis=None):
        a = self.convertAxis(axis)
        self.acceleration[a] = acceleration

    def getSpeed(self, axis=None):
        a = self.convertAxis(axis)
        return self.speed[a]

    def setSpeed(self, speed, axis=None):
        a = self.convertAxis(axis)
        self.speed[a] = speed

    @dummy_log
    def relMove(
        self, mm, speed=None, acceleration=None, wait_for_settling=True, axis=None
    ):
        a = self.convertAxis(axis)
        if self.mirroring.get(a):
            mm = -mm
        self.current_position[a] += mm
        self.moving_dir[a] = "pos" if mm > 0 else "neg" if mm < 0 else None
        return self.getPosition(axis=a)

    @dummy_log
    def absMove(
        self,
        mm,
        speed=None,
        acceleration=None,
        axis=None,
    ):
        a = self.convertAxis(axis)
        if not self.axes_homed[a]:
            self.log.error("%s must home before using absolute movements!", a)
            return self.getPosition(axis=a)
        target = -mm if self.mirroring.get(a) else mm
        self.moving_dir[a] = (
            "pos"
            if target - self.current_position[a] > 0
            else "neg" if target - self.current_position[a] < 0 else None
        )
        self.current_position[a] = target
        return self.getPosition(axis=a)

    @dummy_log
    def startJog(self, speed=None, acceleration=None, axis=None):
        a = self.convertAxis(axis)
        if not self.jogging[a]:
            self.pre_jog_speed[a] = self.getSpeed(axis=a)
            self.pre_jog_acceleration[a] = self.getAcceleration(axis=a)
        self.jogging[a] = True
        if speed is None:
            speed = 0.0
        if self.mirroring.get(a):
            speed = -speed
        self.moving_dir[a] = "pos" if speed > 0 else "neg" if speed < 0 else None
        self.setSpeed(abs(speed), axis=a)
        if acceleration is not None:
            self.setAcceleration(acceleration, axis=a)

    @dummy_log
    def stopJog(self, axis=None):
        a = self.convertAxis(axis)
        self.jogging[a] = False
        self.moving_dir[a] = None
        self.setSpeed(self.pre_jog_speed[a], axis=a)
        self.setAcceleration(self.pre_jog_acceleration[a], axis=a)

    def getLimits(self, axis=None):
        a = self.convertAxis(axis)
        limits = self.limits.get(a, (None, None))
        lower = 0.0 if limits[0] is None else limits[0]
        upper = self.max_travel_mm.get(a, 0.0) if limits[1] is None else limits[1]
        return (lower, upper)

    def setLimits(self, limits=None, axis=None):
        a = self.convertAxis(axis)
        if limits is None:
            limits = self.limits.get(a, (None, None))
        self.limits[a] = limits

    def setup_log_file(self, filename):
        pass

    def logging_start(self):
        self.logging_running = True

    def logging_stop(self):
        self.logging_running = False
