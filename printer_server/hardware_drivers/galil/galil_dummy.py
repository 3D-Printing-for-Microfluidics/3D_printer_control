# -*- coding: utf-8 -*-
"""Galil control module."""
import re
import time
import json
import atexit

# remove bad chars from file name
def cleanFileName(name):
    for c in '\\/:*?"<>| ':
        name = name.replace(c, '')
    return name

# maps X,Y,Z to A,B,C
def convertAxis(axis):
    axis = axis.upper()
    if axis in ('X', 'A'):
        return 'A'
    if axis in ('B', 'Y'):
        return 'B'
    if axis in ('C', 'Z'):
        return 'C'
    raise ValueError('Invalid axis supplied')

# return the value for the specified axis
def parseResponseString(string, axis="A"):
    string = string.replace(',', '')                # get rid of commas in response
    array = string.split()                          # split axes into an array
    axis = convertAxis(axis)                        # sterilize axis input
    axis_index = ord(axis.lower()) - 97             # converts A B C to 0 1 2
    value = array[axis_index]                       # index into the axis we want
    return int(value)

class Galil_dummy():

    # regular expressions for parsing command chains
    waitRegex = re.compile(r'WAIT (-?\d+(\.\d+)?)')
    moveRegex = re.compile(r'^(UP|DOWN) (-?\d+(\.\d+)?) SPEED (-?\d+(\.\d+)?) ACC (-?\d+(\.\d+)?)')

    def __init__(self, address=None, verbose=False):
        print(" galil - __init({}, {})__".format(address, verbose))
        self.verbose = verbose
        self.address = address

        # default configuration parameters
        self.axes = ["A"]
        self.travel = {"A":100}     # max travel in mm
        self.ctspmm = {"A":8000}    # counts/mm for each axis
        self.data = {}              # for saving calibration data
        self.move_num = 0           # also for saving calibration data

        # connection parameters
        self.connected = False
        self.homed = False
        self.controller_name = "DMC31010"   # controller to search for
        atexit.register(self.disconnect)    # register disconnect to always run at interpreter end

    def initialize(self):
        print(" galil - initialize()")
        self.motorOn()

    def goToZmax(self):
        print(" galil - goToZmax()")

    def goToZmin(self):
        print(" galil - goToZmin()")

    def resume(self, layerThickness):
        print(" galil - resume({})".format(layerThickness))

    def goToFirstLayerHeight(self, height):
        print(" galil - goToFirstLayerHeight({})".format(height))
        return 0, height

    def goToPlanarizationPullOff(self):
        print(" galil - goToPlanarizationPullOff()")

    def printCycle(self, layerThicknessMm, commandChain):
        print(" galil - printCycle({}, {})".format(layerThicknessMm, commandChain))

        # keep track of which command is the last down command
        lastDownCommand = 0
        for i, command in enumerate(commandChain):
            m2 = self.moveRegex.fullmatch(command)
            if m2 and m2.group(1) == 'DOWN':
                lastDownCommand = i

        for i, c in enumerate(commandChain):
            print(i, c)

        print("last down is", lastDownCommand)

        # parse the commands and move accordingly
        for i, command in enumerate(commandChain):
            m1 = self.waitRegex.fullmatch(command)
            m2 = self.moveRegex.fullmatch(command)

            if m1:                                              # is a wait command
                wait_seconds = float(m1.group(1))
                time.sleep(wait_seconds)
            elif m2:                                            # is a move command
                direction = m2.group(1)
                distance = float(m2.group(2))
                speed = float(m2.group(4))
                acceleration = float(m2.group(6))
                distance *= -1 if direction == 'UP' else 1      # calculate the sign using direction, up is negative
                if i == lastDownCommand:                        # take off the layer thickness if this is the last layer
                    distance -= layerThicknessMm
                self.relMove(speed=speed, mm=distance, acceleration=acceleration)
        return 0, 0, 0, 0

    def pause(self):
        print(" galil - pause()")

    # find and connect to the Galil controller
    def connect(self):
        print(" galil - connect()")

    # convert mm to counts for the specified axis
    def mmToCnts(self, mm, axis="A"):
        axis = convertAxis(axis)
        return int(mm * self.ctspmm[axis])

    # convert counts to mm for the specified axis
    def cntsToMm(self, counts, axis="A"):
        axis = convertAxis(axis)
        return counts / self.ctspmm[axis]

   # send a command to the controller, interpret errors if any are thrown
    def send(self, command):
        print(" galil - send({})".format(command))

    # check both limit switches, return a tuple with their trip values
    def checkLimits(self, axis="A"):
        print(" galil - checkLimits({})".format(axis))

    # read the current position of the specified encoder
    def getPosition(self, axis="A"):
        print(" galil - getPosition({})".format(axis))

    # turn on the specified axis
    def motorOn(self, axis="A"):
        print(" galil - motorOn({})".format(axis))

    # turn off the specified axis
    def motorOff(self, axis="A"):
        print(" galil - motorOff({})".format(axis))

    # get the acceleration for the specified axis (mm/sec^2)
    def getAcceleration(self, axis="A"):
        print(" galil - getAcceleration({})".format(axis))

    # set the acceleration for the specified axis (mm/sec^2)
    def setAcceleration(self, acceleration, axis="A"):
        print(" galil - setAcceleration({}, {})".format(acceleration, axis))

    # get the speed for the specified axis (mm/sec)
    def getSpeed(self, axis="A"):
        print(" galil - getSpeed({})".format(axis))

    # set the speed for the specified axis (mm/sec)
    def setSpeed(self, speed, axis="A"):
        print(" galil - setSpeed({}, {})".format(speed, axis))

    # run the Galil homing routine
    def home(self, axis="A"):
        print(" galil - home({})".format(axis))

    # blocking call to relative move an axis the specified distance at speed (in mm/sec)
    # pylint: disable=too-many-arguments
    def relMove(self, speed, mm=None, cnts=None, acceleration=None, axis="A"):
        print(" galil - relMove({}, {}, {}, {}, {})".format(speed, mm, cnts, acceleration, axis))

    # blocking call to move specified axis to absolute position at speed (in mm/sec)
    # pylint: disable=too-many-arguments
    def absMove(self, speed, mm=None, cnts=None, acceleration=None, axis="A"):
        print(" galil - absMove({}, {}, {}, {}, {})".format(speed, mm, cnts, acceleration, axis))

    # blocks execution until the encoder reading reaches the specified value. Also logs all position data
    def waitForMotionComplete(self, cnts, axis="A"):
        print(" galil - waitForMotionComplete({}, {})".format(cnts, axis))

    # end connection
    def disconnect(self):
        print(" galil - disconnect()")

    # this only needs to be run once on power up. It will turn off motors which may cause movement, BE CAREFUL
    def configure(self):
        print(" galil - configure()")

    # downlaod a DMC file to the controller
    def downloadProgram(self, filename):
        print(" galil - downloadProgram({})".format(filename))

    # interactive mode - will return a prompt you can issue Galil commands to. Exits with KeyboardInterrupt
    def interactiveMode(self):
        print(" galil - interactiveMode()")
