# -*- coding: utf-8 -*-
"""Galil control module."""
import re
import time


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

    # regular expressions for parsing command chains
    waitRegex = re.compile(r"WAIT (-?\d+(\.\d+)?)")
    moveRegex = re.compile(
        r"^(UP|DOWN) (-?\d+(\.\d+)?) SPEED (-?\d+(\.\d+)?) ACC (-?\d+(\.\d+)?)"
    )

    @dummy_log
    def __init__(self, address=None, verbose=False):
        self.axes = ["A"]
        self.travel = {"A": 100}  # max travel in mm
        self.ctspmm = {"A": 8000}  # counts/mm for each axis

    @dummy_log
    def initialize(self):
        self.motorOn()

    @dummy_log
    def goToZmax(self):
        pass

    @dummy_log
    def goToZmin(self):
        pass

    @dummy_log
    def resume(self, layerThickness):
        pass

    @dummy_log
    def goToFirstLayerHeight(self, height):
        return 0, height

    @dummy_log
    def goToPlanarizationPullOff(self):
        pass

    @dummy_log
    def printCycle(self, layerThicknessMm, commandChain):
        # keep track of which command is the last down command
        lastDownCommand = 0
        for i, command in enumerate(commandChain):
            m2 = self.moveRegex.fullmatch(command)
            if m2 and m2.group(1) == "DOWN":
                lastDownCommand = i

        for i, c in enumerate(commandChain):
            print(i, c)

        print("last down is", lastDownCommand)

        # parse the commands and move accordingly
        for i, command in enumerate(commandChain):
            m1 = self.waitRegex.fullmatch(command)
            m2 = self.moveRegex.fullmatch(command)

            if m1:  # is a wait command
                wait_seconds = float(m1.group(1))
                time.sleep(wait_seconds)
            elif m2:  # is a move command
                direction = m2.group(1)
                distance = float(m2.group(2))
                speed = float(m2.group(4))
                acceleration = float(m2.group(6))
                distance *= (
                    -1 if direction == "UP" else 1
                )  # calculate the sign using direction, up is negative
                if (
                    i == lastDownCommand
                ):  # take off the layer thickness if this is the last layer
                    distance -= layerThicknessMm
                self.relMove(speed=speed, mm=distance, acceleration=acceleration)
        return 0, 0, 0, 0

    @dummy_log
    def pause(self):
        pass

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
        pass

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
        pass

    # pylint: disable=too-many-arguments
    @dummy_log
    def absMove(self, speed, mm=None, cnts=None, acceleration=None, axis="A"):
        pass

    @dummy_log
    def waitForMotionComplete(self, cnts, axis="A"):
        pass

    @dummy_log
    def disconnect(self):
        pass

    @dummy_log
    def configure(self):
        pass

    @dummy_log
    def downloadProgram(self, filename):
        pass

    @dummy_log
    def interactiveMode(self):
        pass
