# -*- coding: utf-8 -*-
"""Galil control module."""
import sys
import time
import json
import atexit
import logging
from datetime import datetime
import gclib
from printer_server.async_file_handler import async_file_hander


def cleanFileName(name):
    """Return a file name without any problematic characters."""
    for c in '\\/:*?"<>| ':
        name = name.replace(c, "")
    return name


def convertAxis(axis):
    """Return converted axis name (maps X,Y,Z to A,B,C)"""
    axis = axis.upper()
    if axis in ("X", "A"):
        return "A"
    if axis in ("B", "Y"):
        return "B"
    if axis in ("C", "Z"):
        return "C"
    raise ValueError("Invalid axis supplied")


def parseResponseString(string, axis="A"):
    """Return an integer representing the value for the specified axis.

    i.g. "12, 15, 20" would return "12" for axis A, "15" for B, etc.
    """
    string = string.replace(",", "")
    array = string.split()
    axis = convertAxis(axis)
    axis_index = ord(axis.lower()) - 97  # converts A B C to 0 1 2
    value = array[axis_index]
    return int(value)


class Galil:
    def __init__(
        self,
        address=None,
        log_level=logging.DEBUG,
        top_position=None,
        bottom_position=None,
        calibration_position=None,
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.movement_log = None

        self.gclib_error = gclib.GclibError

        self.address = address
        self.calibration_position = calibration_position
        self.bottom_position = bottom_position
        self.top_position = top_position
        self.error_window = 1
        self.monitoring_window = 80
        self.jogging = False
        self.pre_jog_speed = 0

        # default configuration parameters
        self.axes = ["A"]
        self.max_travel_mm = {"A": 100}
        self.ctspmm = {"A": 8000}
        self.data = {}
        self.move_num = 0

        # connection parameters
        self.connected = False
        self.homed = False
        self.controller_name = "DMC31010"
        self.g = gclib.py()
        atexit.register(self.disconnect)

    def initialize(self):
        self.motorOn()

    def goToZcalibration(self):
        self.absMove(speed=25, cnts=self.calibration_position)
        return self.getPosition()

    def goToZmax(self):
        self.absMove(speed=25, cnts=self.top_position)
        return self.getPosition()

    def goToZmin(self):
        self.absMove(speed=25, cnts=self.bottom_position)
        return self.getPosition()

    def connect(self):
        """Find the first Galil controller and connect to it."""
        self.log.info("Searching for %s controller...", self.controller_name)
        available = self.g.GAddresses()
        self.address = None
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
                return
        msg = "{} not found.".format(self.controller_name)
        self.log.critical(msg)
        sys.exit(msg)

    def mmToCnts(self, mm, axis="A"):
        """Convert mm to counts for the specified axis."""
        return int(mm * self.ctspmm[convertAxis(axis)])

    def cntsToMm(self, counts, axis="A"):
        """Convert counts to mm for the specified axis."""
        return counts / self.ctspmm[convertAxis(axis)]

    def send(self, command, notify=True):
        """Send a command to the controller.

        If an error is returned, request and also return more
        information about the error.
        """
        if notify:
            self.log.debug("Sent : '%s'", command)
        try:
            response = self.g.GCommand(command)
            response = "".join(response)
            if notify and response != "":
                self.log.debug("Reply: '%s'", response)
            return response
        except self.gclib_error as error:
            error_code = self.g.GCommand("TC 1")
            if error_code not in ("", "0"):
                error = error_code
            self.log.error("Last command '%s' returned error '%s'", command, error)
            return error

    def checkLimits(self, axis="A"):
        """Return a tuple the state of the limit switches for the
        specified axis.
        """
        a = convertAxis(axis)
        lf = self.send("MG _LF{}".format(a), notify=False)
        lr = self.send("MG _LR{}".format(a), notify=False)
        return bool(lf == "0.0000"), bool(lr == "0.0000")

    def getPosition(self, axis="A", notify=True):
        """Return the position of the specified encoder."""
        if axis is None:
            return self.send("TP", notify=notify)
        axis = convertAxis(axis)
        pos = self.send("TP{}".format(axis), notify=notify)
        return int(pos)

    def motorOn(self, axis="A"):
        """Turn on the specified axis."""
        axis = convertAxis(axis)
        self.send("SH{}".format(axis))

    def motorOff(self, axis="A"):
        """Turn off the specified axis."""
        axis = convertAxis(axis)
        self.log.warning("Axis %s motor turned off. It may sink due to gravity.", axis)
        self.send("MO{}".format(axis))

    def getAcceleration(self, axis="A"):
        """Return the acceleration of the specified axis (mm/sec^2)."""
        a = convertAxis(axis)
        response = self.send("AC ?", notify=False)
        acc = parseResponseString(response, a)
        return int(acc) / self.ctspmm[a]

    def setAcceleration(self, acceleration, axis="A"):
        """Set the acceleration for the specified axis (mm/sec^2)."""
        a = convertAxis(axis)
        self.send("AC{}={}".format(a, acceleration * self.ctspmm[a]))
        self.send("DC{}={}".format(a, acceleration * self.ctspmm[a]))

    def getSpeed(self, axis="A"):
        """Return the speed for the specified axis (mm/sec)."""
        a = convertAxis(axis)
        response = self.send("SP ?", notify=False)
        speed = parseResponseString(response, a)
        return int(speed) / self.ctspmm[a]

    def setSpeed(self, speed, axis="A"):
        """Set the speed for the specified axis (mm/sec)."""
        a = convertAxis(axis)
        self.send("SP{}={}".format(a, speed * self.ctspmm[a]))

    def home(self, axis="A"):
        """Run the homing routine.

        The homing routine begins by jogging up until the limit switch
        is triggered, then runs the built in "HM" routine and waits for
        motion to complete.
        """
        self.log.info("Start homing...")
        a = convertAxis(axis)
        self.setSpeed(10)
        self.motorOn()
        self.startJog(speed=-15)
        self.g.GMotionComplete(a)
        self.stopJog()
        self.motorOn()
        self.send("HM")
        self.send("BGA")
        self.waitForMotionComplete(0)
        self.g.GMotionComplete(axis)
        self.homed = True
        self.log.info("Homing complete.")

    # pylint: disable=too-many-arguments
    def relMove(self, mm=None, cnts=None, speed=None, acceleration=None, axis="A"):
        """Perform a relative movement.

        Blocks execution until movement is complete. All units are in mm
        and mm/sec(^2).
        """
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
            self.log.info("Move axis %s to relative position %s", a, cnts)
            self.send("PR{}={}".format(a, cnts))
            self.send("BG{}".format(a))
            self.waitForMotionComplete(start_position + cnts)
        if speed is not None:
            self.setSpeed(old_speed)
        if acceleration is not None:
            self.setAcceleration(old_acceleration)
        return self.getPosition()

    # pylint: disable=too-many-arguments
    def absMove(
        self,
        mm=None,
        cnts=None,
        speed=None,
        acceleration=None,
        wait_for_settling=True,
        axis="A",
    ):
        """Perform an absolute movement.

        Blocks execution until movement is complete. All units are in mm
        and mm/sec(^2). wait_for_settling determines how precise
        the movement has to be.
        """
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
            self.log.info("Move axis %s to absolute position %s", a, cnts)
            self.send("PA{}={}".format(a, cnts))
            self.send("BG{}".format(a))
            self.waitForMotionComplete(cnts, wait_for_settling=wait_for_settling)
        if speed is not None:
            self.setSpeed(old_speed)
        if acceleration is not None:
            self.setAcceleration(old_acceleration)
        return self.getPosition()

    def startJog(self, speed=None, axis="A"):
        """Start a jog, non-blocking."""
        if not self.jogging:
            self.pre_jog_speed = self.getSpeed()  # save the speed before jogging begins
        self.jogging = True
        a = convertAxis(axis)
        self.log.info("Start jog on axis %s at speed %s mm/sec", a, speed)
        self.send("JG{}={}".format(a, speed * self.ctspmm[a]))
        self.send("BG{}".format(a))

    def stopJog(self, axis="A"):
        """Stop a jog, non-blocking."""
        a = convertAxis(axis)
        self.log.info("Stop jog on axis %s", a)
        self.send("ST{}".format(a))
        self.jogging = False
        self.setSpeed(self.pre_jog_speed)

    def waitForMotionComplete(self, cnts, wait_for_settling=True, axis="A"):
        """Blocks execution until the encoder reaches the target value
        and saves motion data as it goes.
        """
        start_time = time.time()
        last_position = self.getPosition(notify=False)  # save the last position
        self.data[self.move_num] = []
        self.data[self.move_num].append(
            {"time": time.time(), "position": last_position, "error_window": -1}
        )
        counter = 0
        time_count = 0
        # wait until we are within 10 um of target
        while not (
            int(cnts - self.monitoring_window)
            <= last_position
            <= int(cnts + self.monitoring_window)
        ):
            if self.movement_log is not None:
                async_file_hander.write(
                    self.movement_log,
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')},",
                )
                async_file_hander.write(
                    self.movement_log,
                    f"{self.cntsToMm(self.getPosition(notify=False))}\n",
                )
            time.sleep(0.001)
            last_position = self.getPosition(notify=False)
            upper, lower = self.checkLimits()
            if (lower and cnts < last_position) or (upper and cnts > last_position):
                self.log.info("Limit switch triggered")
                self.g.GMotionComplete(axis)
                return
            self.data[self.move_num].append(
                {"time": time.time(), "position": last_position, "error_window": -1}
            )
        if wait_for_settling:
            # only proceed when 10 good consecutive counts have been read
            while counter <= 5:
                if self.movement_log is not None:
                    async_file_hander.write(
                        self.movement_log,
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')},",
                    )
                    async_file_hander.write(
                        self.movement_log,
                        f"{self.cntsToMm(self.getPosition(notify=False))}\n",
                    )
                time.sleep(0.001)
                last_position = self.getPosition(notify=False)
                if any(self.checkLimits()):
                    self.log.info("Limit switch triggered")
                    self.g.GMotionComplete(axis)
                    return
                self.data[self.move_num].append(
                    {
                        "time": time.time(),
                        "position": last_position,
                        "error_window": self.error_window,
                    }
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
                if time_count == 100:
                    self.error_window = 2
                if time_count >= 5000:
                    self.log.warning(
                        "Z motor didn't reach position. Got to %s but needed %s",
                        last_position,
                        cnts,
                    )
                    self.error_window = 1
                    break
        else:
            self.g.GMotionComplete(axis)
        self.error_window = 1
        self.data[self.move_num].append(
            {"time": time.time(), "position": last_position, "error_window": -1}
        )
        self.data[self.move_num].append({"duration": time.time() - start_time})
        self.move_num = self.move_num + 1

    def saveMotionData(self, filename=None):
        """Dump the motion data to a file."""
        # save the coefficients for this run
        for coeff in ("KP", "KI", "KD", "IL"):
            response = self.send("{} ?,?,?".format(coeff))
            response = response.replace(",", "")
            response = response.split()
            self.data["{}C".format(coeff)] = response[
                0
            ]  # get C axis which will be at index 2
        if filename is None:
            filename = "galil_data_P={}_I={}_D={}_IL={}.txt".format(
                self.data["KPC"], self.data["KIC"], self.data["KDC"], self.data["ILC"]
            )
        filename = cleanFileName(filename)
        with open(filename, "w") as outfile:
            json.dump(self.data, outfile)

    def disconnect(self):
        """Disconnect form the Galil controller."""
        if self.connected is not False:
            try:
                self.connected = False
                self.g.GClose()
                self.log.info("Disconnected from %s", self.controller_name)
            except self.gclib_error as e:
                self.log.error("Unexpected GclibError on disconnect: %s", e)

    def downloadProgram(self, filename):
        """Download a DMC file to the Galil controller."""
        self.log.info("Downloading '%s' to controller...", filename)
        return self.g.GProgramDownloadFile(filename)

    def interactiveMode(self):
        """Start interactive mode.

        This will leave you on a python prompt that forwards commands to
        the controller. Exits with KeyboardInterrupt.
        """
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

    def set_log_file(self, filename):
        """Set the log file."""
        self.movement_log = filename


if __name__ == "__main__":
    g = Galil(log_level=logging.DEBUG)
    g.connect()
    g.interactiveMode()
