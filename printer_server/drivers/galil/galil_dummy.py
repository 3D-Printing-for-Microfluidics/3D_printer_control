from printer_server.logging_handler import dummy_log


def cleanFileName(name):
    for c in '\\/:*?"<>| ':
        name = name.replace(c, "")
    return name


class Galil_dummy:
    @dummy_log
    def __init__(self, config_dict=None, address=None):
        self.controller_name = config_dict["controller_name"]
        self.default_axis = config_dict["default_axis"]
        self.axes = config_dict["axes"]
        self.axes_common_names = config_dict["axes_common_names"]
        self.max_travel_mm = config_dict["axes_travel"]
        self.ctspmm = config_dict["axes_ctspmm"]
        self.calibration_position = config_dict["calibration_position"]
        self.bottom_position = config_dict["bottom_position"]
        self.top_position = config_dict["top_position"]
        self.tolerence = config_dict["axes_tolerance"]

        self.positions = {}
        for a in self.axes:
            self.positions[a] = 0

    def parseResponseString(self, string, axis):
        """Return an integer representing the value for the specified axis.

        i.g. "12, 15, 20" would return "12" for axis A, "15" for B, etc.
        """
        string = string.replace(",", "")
        array = string.split()
        a = self.convertAxis(axis)
        axis_index = ord(a.lower()) - 97  # converts A B C to 0 1 2
        value = array[axis_index]
        return int(value)

    def convertAxis(self, axis):
        """Return converted axis name (eg. maps X,Y,Z to A,B,C)"""
        if axis is None:
            axis = self.default_axis
        for i in range(len(self.axes)):
            if axis in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
            if axis.upper() in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
        raise ValueError("Invalid axis supplied")

    @dummy_log
    def initialize(self):
        self.motorOn()

    @dummy_log
    def goToZcalibration(self):
        self.positions["A"] = self.calibration_position

    @dummy_log
    def goToZmax(self):
        self.positions["A"] = self.top_position

    @dummy_log
    def goToZmin(self):
        self.positions["A"] = self.bottom_position

    @dummy_log
    def connect(self):
        pass

    def mmToCnts(self, mm, axis="A"):
        axis = self.convertAxis(axis)
        return int(mm * self.ctspmm[axis])

    def cntsToMm(self, counts, axis="A"):
        axis = self.convertAxis(axis)
        return counts / self.ctspmm[axis]

    @dummy_log
    def send(self, command):
        pass

    @dummy_log
    def checkLimits(self, axis="A"):
        pass

    @dummy_log
    def getPosition(self, axis="A"):
        return self.positions[axis]

    @dummy_log
    def motorOn(self, axis="A"):
        pass

    @dummy_log
    def motorOff(self, axis="A"):
        pass

    @dummy_log
    def getAcceleration(self, axis="A"):
        pass

    @dummy_log
    def setAcceleration(self, acceleration, axis="A"):
        pass

    @dummy_log
    def getSpeed(self, axis="A"):
        pass

    @dummy_log
    def setSpeed(self, speed, axis="A"):
        pass

    @dummy_log
    def home(self, axis="A"):
        pass

    @dummy_log
    def relMove(self, mm=None, cnts=None, speed=None, acceleration=None, axis="A"):
        if mm is not None:
            self.positions[axis] += self.mmToCnts(mm)
        elif cnts is not None:
            self.positions[axis] += cnts

    # pylint: disable=too-many-arguments
    @dummy_log
    def absMove(
        self,
        mm=None,
        cnts=None,
        speed=None,
        acceleration=None,
        wait_for_settling=True,
        axis="A",
    ):
        if mm is not None:
            self.positions[axis] = self.mmToCnts(mm)
        elif cnts is not None:
            self.positions[axis] = cnts

    @dummy_log
    def startJog(self, speed=None, axis="A"):
        pass

    @dummy_log
    def stopJog(self, axis="A"):
        pass

    @dummy_log
    def waitForMotionComplete(self, cnts, wait_for_settling=True, axis="A"):
        pass

    @dummy_log
    def saveMotionData(self, filename=None):
        pass

    @dummy_log
    def disconnect(self):
        pass

    @dummy_log
    def downloadProgram(self, filename):
        pass

    @dummy_log
    def interactiveMode(self):
        pass

    @dummy_log
    def set_log_file(self, filename):
        pass
