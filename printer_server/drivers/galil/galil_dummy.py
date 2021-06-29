from printer_server.logging_handler import dummy_log


def cleanFileName(name):
    for c in '\\/:*?"<>| ':
        name = name.replace(c, "")
    return name


def convertAxis(axis):
    axis = axis.upper()
    if axis in ("X", "A"):
        return "A"
    if axis in ("B", "Y"):
        return "B"
    if axis in ("C", "Z"):
        return "C"
    raise ValueError("Invalid axis supplied")


# return the value for the specified axis
def parseResponseString(string, axis="A"):
    string = string.replace(",", "")  # get rid of commas in response
    array = string.split()  # split axes into an array
    axis = convertAxis(axis)  # sterilize axis input
    axis_index = ord(axis.lower()) - 97  # converts A B C to 0 1 2
    value = array[axis_index]  # index into the axis we want
    return int(value)


class Galil_dummy:
    @dummy_log
    def __init__(self, address=None):
        self.axes = ["A"]
        self.travel = {"A": 100}  # max travel in mm
        self.ctspmm = {"A": 8000}  # counts/mm for each axis
        self.position = 0
        self.bottom_position = 368000
        self.top_position = -400000

    @dummy_log
    def initialize(self):
        self.motorOn()

    @dummy_log
    def goToZmax(self):
        self.position = -400000

    @dummy_log
    def goToZmin(self):
        self.position = 368000

    @dummy_log
    def connect(self):
        pass

    def mmToCnts(self, mm, axis="A"):
        axis = convertAxis(axis)
        return int(mm * self.ctspmm[axis])

    def cntsToMm(self, counts, axis="A"):
        axis = convertAxis(axis)
        return counts / self.ctspmm[axis]

    @dummy_log
    def send(self, command):
        pass

    @dummy_log
    def checkLimits(self, axis="A"):
        pass

    @dummy_log
    def getPosition(self, axis="A"):
        return self.position

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
    def relMove(self, speed, mm=None, cnts=None, acceleration=None, axis="A"):
        if mm is not None:
            self.position += self.mmToCnts(mm)
        elif cnts is not None:
            self.position += cnts

    # pylint: disable=too-many-arguments
    @dummy_log
    def absMove(self, mm=None, cnts=None, speed=None, acceleration=None, axis="A"):
        if mm is not None:
            self.position = self.mmToCnts(mm)
        elif cnts is not None:
            self.position = cnts

    @dummy_log
    def startJog(self, speed=None, axis="A"):
        pass

    @dummy_log
    def stopJog(self, axis="A"):
        pass

    @dummy_log
    def waitForMotionComplete(self, cnts, axis="A"):
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
