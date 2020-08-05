# -*- coding: utf-8 -*-
"""Galil control module."""
import sys
import time
import json
import atexit
import logging
from pathlib import Path
from datetime import datetime

# remove bad chars from file name
def cleanFileName(name):
    for c in '\\/:*?"<>| ':
        name = name.replace(c, "")
    return name


# maps X,Y,Z to A,B,C
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
    string = string.replace(",", "")
    array = string.split()
    axis = convertAxis(axis)
    axis_index = ord(axis.lower()) - 97  # converts A B C to 0 1 2
    value = array[axis_index]
    return int(value)


class Galil:
    def __init__(self, address=None, log_level=logging.DEBUG):

        # import here so test system doesn't have to install gclib
        import gclib

        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.gclib_error = gclib.GclibError

        self.address = address
        self.bottom_position = 368000
        self.top_position = -400000
        self.error_window = 1
        self.jogging = False
        self.pre_jog_speed = 0

        # default configuration parameters
        self.axes = ["A"]
        self.travel = {"A": 100}  # max travel in mm
        self.ctspmm = {"A": 8000}  # counts/mm for each axis
        self.data = {}
        self.move_num = 0

        # connection parameters
        self.connected = False
        self.homed = False
        self.controller_name = "DMC31010"
        self.g = gclib.py()
        atexit.register(self.disconnect)

        # a log to track all communications for debugging, gets created on connect
        self.log_file = Path.cwd() / "logs"

    def initialize(self):
        self.motorOn()

    def goToZmax(self):
        self.absMove(speed=25, cnts=self.top_position)
        self.waitForMotionComplete(self.top_position)
        return self.getPosition()

    def goToZmin(self):
        self.absMove(speed=25, cnts=self.bottom_position)
        self.waitForMotionComplete(self.bottom_position)
        return self.getPosition()

    # find and connect to the Galil controller
    def connect(self):
        # Get Ethernet controllers requesting IP addresses
        self.log.info("Searching for %s controller...", self.controller_name)
        available = self.g.GAddresses()
        self.address = None
        # If there is more than one controller connected, this will only connect to the first
        for address in sorted(available.keys()):
            if self.controller_name in available[address]:
                self.address = address.strip("()")
                self.controller_name = available[address]
                self.log.debug("Found %s at %s", available[address], self.address)
                self.log.info(
                    "Connecting to %s at %s", self.controller_name, self.address
                )
                self.g.GOpen("{} --direct".format(self.address))
                self.log.debug("GInfo returned: %s", self.g.GInfo())
                self.connected = True

                # Create log
                date_and_time = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
                self.log_file = str(
                    self.log_file
                    / "galil_controller_command_dump_{}.txt".format(date_and_time)
                )
                return
        msg = "{} not found.".format(self.controller_name)
        self.log.critical(msg)
        sys.exit(msg)

    # convert mm to counts for the specified axis
    def mmToCnts(self, mm, axis="A"):
        axis = convertAxis(axis)
        return int(mm * self.ctspmm[axis])

    # convert counts to mm for the specified axis
    def cntsToMm(self, counts, axis="A"):
        axis = convertAxis(axis)
        return counts / self.ctspmm[axis]

    # send a command to the controller, interpret errors if any are thrown
    def send(self, command, notify=True):
        with open(self.log_file, "a") as f:
            if notify:
                self.log.debug("Sent : '%s'", command)
                f.write("Sent : '{}'\n".format(command))
            try:
                response = self.g.GCommand(command)
                response = "".join(response)
                if notify and response != "":
                    self.log.debug("Reply: '%s'", response)
                    f.write("Reply: '{}'\n".format(response))
                return response
            except self.gclib_error as error:
                error_code = self.g.GCommand("TC 1")
                if error_code not in ("", "0"):
                    error = error_code
                self.log.error("Last command '%s' returned error '%s'", command, error)
                return error

    # check both limit switches, return a tuple with their trip values
    def checkLimits(self, axis="A"):
        a = convertAxis(axis)
        lf = self.send("MG _LF{}".format(a), notify=False)
        lr = self.send("MG _LR{}".format(a), notify=False)
        return bool(lf == "0.0000"), bool(lr == "0.0000")

    # read the current position of the specified encoder
    def getPosition(self, axis="A", notify=True):
        if axis is None:
            return self.send("TP", notify=notify)
        axis = convertAxis(axis)
        pos = self.send("TP{}".format(axis), notify=notify)
        return int(pos)

    # turn on the specified axis
    def motorOn(self, axis="A"):
        axis = convertAxis(axis)
        self.send("SH{}".format(axis))

    # turn off the specified axis
    def motorOff(self, axis="A"):
        axis = convertAxis(axis)
        self.send("MO{}".format(axis))

    # get the acceleration for the specified axis (mm/sec^2)
    def getAcceleration(self, axis="A"):
        a = convertAxis(axis)
        response = self.send("AC ?", notify=False)
        acc = parseResponseString(response, a)
        return int(acc) / self.ctspmm[a]

    # set the acceleration for the specified axis (mm/sec^2)
    def setAcceleration(self, acceleration, axis="A"):
        a = convertAxis(axis)
        self.send("AC{}={}".format(a, acceleration * self.ctspmm[a]))
        self.send("DC{}={}".format(a, acceleration * self.ctspmm[a]))

    # get the speed for the specified axis (mm/sec)
    def getSpeed(self, axis="A"):
        a = convertAxis(axis)
        response = self.send("SP ?", notify=False)
        speed = parseResponseString(response, a)
        return int(speed) / self.ctspmm[a]

    # set the speed for the specified axis (mm/sec)
    def setSpeed(self, speed, axis="A"):
        a = convertAxis(axis)
        self.send("SP{}={}".format(a, speed * self.ctspmm[a]))

    # run the Galil homing routine
    def home(self, axis="A"):
        a = convertAxis(axis)
        self.motorOn()  # turn motor on
        self.startJog(speed=-15)  # move up until the limit switch is triggered
        self.g.GMotionComplete(a)  # block until motion planning is complete
        self.stopJog()  # restores pre-jog speed
        self.motorOn()  # turn motor back on (limit switch was tripped, which turns it off)
        self.send("HM")  # send home command
        self.send("BGA")  # start homing
        # block until motion is complete (encoder is set to 0 at end of homing)
        self.waitForMotionComplete(0)
        self.homed = True  # update class homed status

    # blocking call to relative move an axis the specified distance at speed (in mm/sec)
    # pylint: disable=too-many-arguments
    def relMove(self, mm=None, cnts=None, speed=None, acceleration=None, axis="A"):
        a = convertAxis(axis)  # check that the axis is valid
        old_speed = None
        old_acceleration = None
        if speed is not None:
            old_speed = self.getSpeed()
            self.setSpeed(speed)
        if acceleration is not None:
            old_acceleration = self.getAcceleration()
            self.setAcceleration(acceleration)
        if mm is not None:
            cnts = self.mmToCnts(mm)
        if cnts is not None:
            start_position = self.getPosition()
            self.send("PR{}={}".format(a, cnts))
            self.send("BG{}".format(a))
            self.waitForMotionComplete(start_position + cnts)
        if speed is not None:
            self.setSpeed(old_speed)
        if acceleration is not None:
            self.setAcceleration(old_acceleration)
        return self.getPosition()

    # blocking call to move specified axis to absolute position at speed (in mm/sec)
    # pylint: disable=too-many-arguments
    def absMove(self, mm=None, cnts=None, speed=None, acceleration=None, axis="A"):
        if not self.homed:
            msg = "Must home before using absolute movements!"
            self.log.critical(msg)
            sys.exit(msg)
        a = convertAxis(axis)
        old_speed = None
        old_acceleration = None
        if speed is not None:
            old_speed = self.getSpeed()
            self.setSpeed(speed)
        if acceleration is not None:
            old_acceleration = self.getAcceleration()
            self.setAcceleration(acceleration)
        if mm is not None:
            cnts = self.mmToCnts(mm)
        if cnts is not None:
            self.send("PA{}={}".format(a, cnts))
            self.send("BG{}".format(a))
            self.waitForMotionComplete(cnts)
        if speed is not None:
            self.setSpeed(old_speed)
        if acceleration is not None:
            self.setAcceleration(old_acceleration)
        return self.getPosition()

    # nonbocking call that start the axis moving at a specified speed.
    def startJog(self, speed=None, axis="A"):
        if not self.jogging:
            self.pre_jog_speed = self.getSpeed()  # save the speed before jogging begins
        self.jogging = True
        a = convertAxis(axis)
        self.send("JG{}={}".format(a, speed * self.ctspmm[a]))
        self.send("BG{}".format(a))

    # nonbocking call that stops the motion of the stage.
    def stopJog(self, axis="A"):
        a = convertAxis(axis)
        self.send("ST{}".format(a))
        self.jogging = False
        self.setSpeed(self.pre_jog_speed)

    # block execution until the encoder reading reaches target.
    # Also notifys all position data
    def waitForMotionComplete(self, cnts, axis="A"):
        start_time = time.time()
        last_position = self.getPosition(notify=False)  # save the last position
        self.data[self.move_num] = []
        self.data[self.move_num].append({"time": time.time(), "position": last_position})
        counter = 0
        time_count = 0
        # only proceed when 10 good consecutive counts have been read
        while counter <= 10:
            time.sleep(0.001)
            last_position = self.getPosition(notify=False)
            if any(self.checkLimits()):
                self.log.warning("Limit switch triggered")
                self.g.GMotionComplete(axis)
                return
            self.data[self.move_num].append(
                {"time": time.time(), "position": last_position}
            )
            if (
                int(cnts - self.error_window)
                <= last_position
                <= int(cnts + self.error_window)
            ):
                counter += 1
            else:
                counter = 0
            time_count += 1
            # timeout for collecting data, motor won't reach position
            if time_count >= 10000:
                self.log.warning(
                    "Z motor didn't reach position. Got to %s but needed %s",
                    last_position,
                    cnts,
                )
                with open(self.log_file, "a") as f:
                    f.write(
                        "Warning - possible position error got to {} needed {}".format(
                            last_position, cnts
                        )
                    )
                break
        self.data[self.move_num].append({"time": time.time(), "position": last_position})
        self.data[self.move_num].append({"duration": time.time() - start_time})
        self.move_num = self.move_num + 1

    # save motion data to a file
    def saveMotionData(self, filename=None):
        # save the coefficients for this run
        for coeff in ("KP", "KI", "KD", "IL"):
            response = self.send("{} ?,?,?".format(coeff))
            response = response.replace(",", "")
            response = response.split()
            self.data["{}C".format(coeff)] = response[
                2
            ]  # get C axis which will be at index 2
        if filename is None:
            filename = "galil_data_P={}_I={}_D={}_IL={}.txt".format(
                self.data["KPC"], self.data["KIC"], self.data["KDC"], self.data["ILC"]
            )
        filename = cleanFileName(filename)
        with open(filename, "w") as outfile:
            json.dump(self.data, outfile)

    # end connection
    def disconnect(self):
        if self.connected is not False:
            try:
                self.connected = False
                self.g.GClose()
                self.log.info("Disconnected from %s", self.controller_name)
            except self.gclib_error as e:
                self.log.error("Unexpected GclibError on disconnect: %s", e)

    # downlaod a DMC file to the controller
    def downloadProgram(self, filename):
        self.log.info("Downloading '%s' to controller...", filename)
        return self.g.GProgramDownloadFile(filename)

    # interactive mode - will return a prompt you can issue Galil commands to.
    # Exits with KeyboardInterrupt
    def interactiveMode(self):
        if not self.connected:
            msg = "Must be connected to Galil controller to run interactive mode"
            self.log.critical(msg)
            sys.exit(msg)
        try:
            while True:
                cmd = input("Give Galil a command>> ")
                cmd.strip()
                print(self.send(cmd.upper()))
        except KeyboardInterrupt:
            print("\nExited by KeyboardInterrupt")


# runs if called from the console
if __name__ == "__main__":
    g = Galil(log_level=logging.DEBUG)
    g.connect()
    g.interactiveMode()
