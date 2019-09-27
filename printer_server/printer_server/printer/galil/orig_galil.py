# -*- coding: utf-8 -*-
"""Galil control module."""
import time
import gclib

class Galil():
    def __init__(self, address=None, verbose=False):
        self.verbose = verbose
        self.address = address

        # default configuration parameters
        self.axes = ["A", "B", "C"]
        self.travel = {"A":300, "B":100, "C":100}
        self.ctspmm = {"A":51200, "B":51200, "C":8000}
        self.speed = 20
        self.acceleration = 500

        # connection parameters
        self.connected = False
        self.controller_name = "DMC4040"    # controller to search for
        self.g = gclib.py()                 # make an instance of the gclib python class

    def __del__(self):
        self.disconnect()

    def connect(self):
        # Get Ethernet controllers requesting IP addresses
        print("Searching for %s controller..." % self.controller_name)
        available = self.g.GAddresses()
        self.address = None

        # If there is more than one DMC4040 connected, this will only connect to the first
        for address in sorted(available.keys()):
            if self.controller_name in available[address]:
                self.address = address.strip('()')          # remove parentheses
                self.controller_name = available[address]
                if self.verbose: print("Found", available[address], "at", self.address)
                print("Connecting to %s at %s" % (self.controller_name, self.address))
                self.g.GOpen("%s --direct" % self.address)
                if self.verbose: print("GInfo returned:", self.g.GInfo())
                self.connected = True
                return True
        print(self.controller_name, "not found.")
        return False    # no controller found

    # maps X,Y,Z to A,B,C
    def convertAxis(self, axis):
        axis = axis.upper()
        # if axis == 'X'or axis == 'A':
        if axis in ('X', 'A'):
            return 'A'
        if axis in ('B', 'Y'):
            return 'B'
        if axis in ('C', 'Z'):
            return 'C'
        raise ValueError('Invalid axis supplied')

    # turn on the specified axis
    def axisOn(self, axis):
        axis = self.convertAxis(axis)   # make sure a valid axis was supplied
        self.send("SH%s" % axis)        # send the motor enable command

    # turn off the specified axis
    def axisOff(self, axis):
        axis = self.convertAxis(axis)   # make sure a valid axis was supplied
        self.send("MO%s" % axis)        # send the motor off command

    # convert mm to counts for the specified axis
    def mmToCnts(self, axis, mm):
        axis = self.convertAxis(axis)
        return int(mm * self.ctspmm[axis])

    # convert counts to mm for the specified axis
    def cntsToMm(self, axis, counts):
        axis = self.convertAxis(axis)
        return counts / self.ctspmm[axis]

    # blocking call to move an axis by specified number of mm
    def relMove(self, axis, mm=None, cnts=None):
        axis = self.convertAxis(axis)           # check that the axis is valid
        if mm is not None:                      # if mm were supplied
            cnts = self.mmToCnts(axis, mm)      # convert to counts
        if cnts is not None:                    # if counts has been calculated or supplied
            self.send("PR%s=%s" % (axis, cnts)) # set the motion on the controler
            self.send("BG%s" % axis)            # begin motion
            self.g.GMotionComplete(axis)        # block until motion is complete

    # blocking call to move specified acis to defined position
    def absMove(self, axis, mm=None, cnts=None):
        axis = self.convertAxis(axis)           # check that the axis is valid
        if mm is not None:                      # if mm were supplied
            cnts = self.mmToCnts(axis, mm)      # convert to counts
        if cnts is not None:                    # if counts has been calculated or supplied
            self.send("PA%s=%s" % (axis, cnts)) # set the motion on the controler
            self.send("BG%s" % axis)            # begin motion
            self.g.GMotionComplete(axis)        # block until motion is complete

    def disconnect(self):
        if self.connected is not False:
            try:
                self.connected = False
                # self.g.GCommand("MO")   # turn off all motors
                self.g.GClose()         # don't forget to close connections!
                if self.verbose: print("Disconnected from", self.controller_name)
            except gclib.GclibError as e:
                print('Unexpected GclibError on disconnect:', e)

    def downloadProgram(self, filename):
        print("Downloading \"%s\" to controller..." % filename)
        return self.g.GProgramDownloadFile(filename)

    def send(self, command):
        if self.verbose: print("Sent : '%s'" % command)                 # print send command if in verbose mode
        try:
            response = self.g.GCommand(command)                         # send the command and save the response
            response = ''.join(response)                                # join the returned char array into a string
            if self.verbose and response != '': print("Reply: '%s'" % response)            # print the response if in verbose mode
            return response                                             # return the response
        except gclib.GclibError as error:                               # if there is an error, return the error
            print("Error: Last command '%s' returned error '%s'" %(command, error))
            return error

    def setSpeed(self, speed, axis=None):
        self.speed = speed
        axes_to_update = axis or self.axes              # if no axis is specified, defaults to all axes
        for a in axes_to_update:
            self.send("SP%s=%s" % (a, speed*self.ctspmm[a]))           # set speed (mm/sec)

    def setAcceleration(self, acceleration, axis=None):
        self.acceleration = acceleration
        axes_to_update = axis or self.axes              # if no axis is specified, defaults to all axes
        for a in axes_to_update:
            self.send("AC%s=%s" % (a, acceleration*self.ctspmm[a]))    # set acceleration
            self.send("DC%s=%s" % (a, acceleration*self.ctspmm[a]))    # set deceleration
            self.send("SD%s=%s" % (a, acceleration*self.ctspmm[a]))    # set switch deceleration

    # this only needs to be run once on power up. It will turn off motors though
    def configure(self):
        # define constants

        self.send("RSPEED=10")
        self.send("ECYCLE = 2048")
        self.send("LBACKOFF=5")

        # set default motion parameters on all axes
        for a in self.axes:
            self.send("SP%s=%s" % (a, self.speed*self.ctspmm[a]))           # set speed (mm/sec)
            self.send("AC%s=%s" % (a, self.acceleration*self.ctspmm[a]))    # set acceleration
            self.send("DC%s=%s" % (a, self.acceleration*self.ctspmm[a]))    # set deceleration
            self.send("SD%s=%s" % (a, self.acceleration*self.ctspmm[a]))    # set switch deceleration

        self.send("MO")     # Turn off motors (Motors must be off to set AG)
        self.send("TM 1000.0000")
        self.send("AG 1, 1, 1")
        self.send("OF 0.0000, 0.0000, 0.0000")
        self.send("AU 0.0, 0.0, 0.0")
        self.send("LD 0, 0, 0")
        self.send("OE 1, 1, 1")
        self.send("CN 1.0000, -1.0000, -1.0000")
        self.send("AF 11, 11, 0")
        self.send("CE 0, 0, 0")
        self.send("MT 1.0, 1.0, 1.0")
        self.send("BW 0, 0, 0")
        self.send("FL 2147483647, 2147483647, 2147483647")
        self.send("BL -2147483648, -2147483648, -2147483648")

        # Tuning Setup
        self.send("KP 1.00, 1.25, 20")
        self.send("KI 0.0400, 0.0498, 1")
        self.send("KD 12.00, 8.00, 64.00 ")   # was KD 12.00, 40

        self.send("FA 0, 0, 0")
        self.send("FV 0, 0, 0")
        self.send("IL 9.9982, 9.9982, 9.9982")
        self.send("PL 0.0000, 0.0000, 0.0000")
        self.send("NB 0.5, 0.5")
        self.send("NF 0, 0")

        # Limits
        self.send("TK 8.5, 8.5, 8.5")
        self.send("TL 4.2, 4.2, 4.2")
        self.send("ER 102400, 51200, 8000")

        # Motion Settings
        self.send("HV 25600, 25600, 4000")
        self.send("IT 0.5000, 0.5000, 0.5000")
        self.send("LC 0, 0, 0")
        self.send("YA 2, 2, 2")
        self.send("BM 2000.0000, 2000.0000, 2000.0000")
        self.send("BX< 200")
        self.send("BI 0, 0, 0")

    # # incrementally increase speed and move all axes
    def sampleMove(self):
        self.send("SH")     # enable all motors
        speed = 100
        for i in range(1, 2):
            print("Pass %s: Speed set to" % i, i*speed)
            self.setSpeed(i*speed)
            self.cycleAxis()

    # runs a rampm movement on the C (Z) axis - useful for optical calibration
    def rampZ(self, stepSize=1, numSteps=10):
        self.send("PRC=%d" % stepSize)
        for _ in range(0, numSteps):
            self.send("BGC")
            time.sleep(2)
        self.send("PRC=-%d" % stepSize)
        for _ in range(0, numSteps):
            self.send("BGC")
            time.sleep(.5)

    # read the current position on all 3 encoders
    def getPosition(self):
        return self.send("DP ?,?,?")

    # move the specified axis to full positive then full negative position
    def cycleAxis(self, axis=None):
        axes_to_update = axis or self.axes              # if no axis is specified, defaults to all axes
        for a in axes_to_update:
            self.send("PR%s=%s" % (a, self.travel[a]* self.ctspmm[a]))  # set relative position to full positive
        for a in axes_to_update:
            self.send("BG%s" % a)                                       # begin motion on axis
        for a in axes_to_update:
            self.g.GMotionComplete("%s" % a)                            # block until motion complete
        for a in axes_to_update:
            self.send("PR%s=-%s" % (a, self.travel[a] * self.ctspmm[a]))# set relative position to full negative
        for a in axes_to_update:
            self.send("BG%s" % a)                                       # begin motion on axis
        for a in axes_to_update:
            self.g.GMotionComplete("%s" % a)                            # block until full motion complete

# runs if called from the console
if __name__ == '__main__':
    g = Galil(verbose=True)
    g.connect()
    # import pdb; pdb.set_trace()
    # g.configure()
    # g.sampleMove()

    try:
        while True:
            cmd = input("Give galil a command>> ")
            cmd.strip()
            if cmd.startswith("ramp"):
                cmd_a = cmd.split()
                g.rampZ(int(cmd_a[1]), int(cmd_a[2]))
            else:
                g.send(cmd.upper())
    except KeyboardInterrupt:
        pass

    print("Done")
