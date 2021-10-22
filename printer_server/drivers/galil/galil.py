# -*- coding: utf-8 -*-
"""Galil control module."""
import sys
import time
import json
import atexit
import logging
from datetime import datetime
from printer_server.async_file_handler import async_file_hander

# remove bad chars from file name
def cleanFileName(name):
    for c in '\\/:*?"<>| ':
        name = name.replace(c, "")
    return name


# maps X,Y,Z to A,B,C
def convertAxis(axis):
    axis = axis.upper()
    if axis in ("A", "X"):
        return "A"
    if axis in ("B", "Y"):
        return "B"
    if axis in ("C", "Z"):
        return "C"
    if axis in ("D", "BP"):
        return "D"
    raise ValueError("Invalid axis supplied")


# return the value for the specified axis
def parseResponseString(string, axis="D"):
    string = string.replace(",", "")
    array = string.split()
    a = convertAxis(axis)
    axis_index = ord(a.lower()) - 97  # converts A B C to 0 1 2
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

        # import here so test system doesn't have to install gclib
        import gclib

        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.movement_log = None

        self.gclib_error = gclib.GclibError

        self.address = address
        self.calibration_position = calibration_position
        self.bottom_position = bottom_position
        self.top_position = top_position
        self.jogging = False
        self.pre_jog_speed = 0
        self.error_window = 0.125 * 51200 / 1000
        self.monitoring_window = 10 * 51200 / 1000

        # default configuration parameters
        self.axes = ["A", "B", "C", "D"]
        self.travel = {"A": 300, "B": 100, "C": 100, "D": 100}  # max travel in mm
        self.ctspmm = {
            "A": 51200,
            "B": 51200,
            "C": 51200,
            "D": 51200,
        }  # counts/mm for each axis
        self.data = {}
        self.move_num = 0

        # connection parameters
        self.connected = False
        self.controller_name = "DMC4040"
        self.g = gclib.py()
        atexit.register(self.disconnect)

        # self.bottom_position = 2355200
        # self.top_position = -2560000

        self.homed = {}
        self.jogging = {}
        self.pre_jog_speed = {}
        for a in self.axes:
            self.homed[a] = False
            self.jogging[a] = False
            self.pre_jog_speed[a] = 0

    def initialize(self):
        for axis in self.axes:
            self.motorOn(axis)

    def goToZcalibration(self, axis="D"):
        self.absMove(speed=25, cnts=self.calibration_position, axis=axis)
        return self.getPosition(axis=axis)

    def goToZmax(self, axis="D"):
        self.absMove(speed=25, cnts=self.top_position, axis=axis)
        return self.getPosition(axis=axis)

    def goToZmin(self, axis="D"):
        self.absMove(speed=25, cnts=self.bottom_position, axis=axis)
        return self.getPosition(axis=axis)

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
                return
        msg = "{} not found.".format(self.controller_name)
        self.log.critical(msg)
        sys.exit(msg)

    # convert mm to counts for the specified axis
    def mmToCnts(self, mm, axis="D"):
        a = convertAxis(axis)
        return int(mm * self.ctspmm[a])

    # convert counts to mm for the specified axis
    def cntsToMm(self, counts, axis="D"):
        a = convertAxis(axis)
        return counts / self.ctspmm[a]

    # send a command to the controller, interpret errors if any are thrown
    def send(self, command, notify=True):
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

    # check both limit switches, return a tuple with their trip values
    def checkLimits(self, axis="D"):
        a = convertAxis(axis)
        lf = self.send("MG _LF{}".format(a), notify=False)
        lr = self.send("MG _LR{}".format(a), notify=False)
        return bool(lf == "0.0000"), bool(lr == "0.0000")

    # read the current position of the specified encoder
    def getPosition(self, axis="D", notify=True):
        if axis is None:
            return self.send("TP", notify=notify)
        a = convertAxis(axis)
        pos = self.send("TP{}".format(a), notify=notify)
        return int(pos)

    def get_focus_position(self):
        galil_position = self.getPosition(axis="Z")
        return int(self.cntsToMm(galil_position) * 1000)

    # turn on the specified axis
    def motorOn(self, axis="D"):
        a = convertAxis(axis)
        self.send("SH{}".format(a))

    # turn off the specified axis
    def motorOff(self, axis="D"):
        a = convertAxis(axis)
        self.log.warning("Axis %s motor turned off. It may sink due to gravity.", a)
        self.send("MO{}".format(a))

    # get the acceleration for the specified axis (mm/sec^2)
    def getAcceleration(self, axis="D"):
        a = convertAxis(axis)
        response = self.send("AC ?,?,?,?", notify=False)
        acc = parseResponseString(response, axis=a)
        return int(acc) / self.ctspmm[a]

    # set the acceleration for the specified axis (mm/sec^2)
    def setAcceleration(self, acceleration, axis="D"):
        a = convertAxis(axis)
        self.send("AC{}={}".format(a, acceleration * self.ctspmm[a]))
        self.send("DC{}={}".format(a, acceleration * self.ctspmm[a]))

    # get the speed for the specified axis (mm/sec)
    def getSpeed(self, axis="D"):
        a = convertAxis(axis)
        response = self.send("SP ?,?,?,?", notify=False)
        speed = parseResponseString(response, axis=a)
        return int(speed) / self.ctspmm[a]

    # set the speed for the specified axis (mm/sec)
    def setSpeed(self, speed, axis="D"):
        a = convertAxis(axis)
        self.send("SP{}={}".format(a, speed * self.ctspmm[a]))

    # run the Galil homing routine
    # def home(self, axis="A"):
    #     self.log.info("Start homing...")
    #     a = convertAxis(axis)
    #     # if the server was improperly shutdown, the speed might need resetting
    #     self.setSpeed(10)
    #     self.motorOn()  # turn motor on
    #     self.startJog(speed=-15)  # move up until the limit switch is triggered
    #     self.g.GMotionComplete(a)  # block until motion planning is complete
    #     self.stopJog()  # restores pre-jog speed
    #     self.motorOn()  # turn motor back on (limit switch was tripped, which turns it off)
    #     self.send("HM")  # send home command
    #     self.send("BGA")  # start homing
    #     # block until motion is complete (encoder is set to 0 at end of homing)
    #     self.waitForMotionComplete(0)
    #     self.g.GMotionComplete(axis)
    #     self.homed = True  # update class homed status
    #     self.log.info("Homing complete.")
    # def home(self, axis="D"):
    #     self.log.info("Start homing...")
    #     a = convertAxis(axis)

    #     self.motorOn(axis=a)  # turn motor on

    #     save_speed = self.getSpeed(axis=a)
    #     self.log.info("Start jog on axis %s at speed %s mm/sec", a, -15)
    #     self.send("JG{}={}".format(a, -15 * self.ctspmm[a]))
    #     self.send("FI{}".format(a))
    #     self.send("BG{}".format(a))
    #     self.g.GMotionComplete(a)  # block until motion planning is complete

    #     if any(self.checkLimits(axis=a)):
    #         self.relMove(mm=(self.travel[a] * 0.55), axis=a)
    #         self.send("BG{}".format(a))
    #         self.g.GMotionComplete(a)  # block until motion planning is complete
    #     else:
    #         self.relMove(mm=(self.travel[a] * 0.05), axis=a)
    #         self.send("BG{}".format(a))
    #         self.g.GMotionComplete(a)  # block until motion planning is complete

    #     self.log.info("Start jog on axis %s at speed %s mm/sec", a, -0.5)
    #     self.send("JG{}={}".format(a, -0.5 * self.ctspmm[a]))
    #     self.send("FI{}".format(a))
    #     self.send("BG{}".format(a))
    #     self.g.GMotionComplete(a)  # block until motion planning is complete

    #     self.setSpeed(save_speed, axis=a)
    #     self.homed[a] = True  # update class homed status
    #     self.log.info("Homing complete.")
    # def home(self, axis="D"):
    #     self.log.info("Start homing - %s...", axis)
    #     a = convertAxis(axis)
    #     self.send("XQ #HM{},0".format(a))
    #     self.g.GMotionComplete(a)  # block until motion planning is complete
    #     self.homed[a] = True  # update class homed status
    #     self.log.info("Homing complete - %s.", axis)

    def home_all(self):
        self.log.info("Start homing...")
        self.send("XQ #HMA,0")
        self.send("XQ #HMB,1")
        self.send("XQ #HMC,2")
        self.send("XQ #HMD,3")

        time.sleep(10)

        for a in self.axes:
            self.g.GMotionComplete(a)
            self.homed[a] = True  # update class homed status
        self.log.info("Homing complete.")

    # def home(self, axis="D"):
    #     self.log.info("Start homing...")
    #     a = convertAxis(axis)

    #     upper, lower = self.checkLimits(axis=a)
    #     if not lower:
    #         self.send("JG{}={}".format(a, -self.mmToCnts(50, axis=a)))
    #         self.send("BG{}".format(a))
    #         self.g.GMotionComplete(a)

    #     self.send("JG{}={}".format(a, self.mmToCnts(25, axis=a)))
    #     self.send("FI{}".format(a))
    #     self.send("BG{}".format(a))
    #     self.g.GMotionComplete(a)

    #     self.send("PR{}={}".format(a, self.mmToCnts(2, axis=a)))
    #     self.send("BG{}".format(a))
    #     self.g.GMotionComplete(a)

    #     self.send("JG{}={}".format(a, -self.mmToCnts(1, axis=a)))
    #     self.send("FI{}".format(a))
    #     self.send("BG{}".format(a))
    #     self.g.GMotionComplete(a)

    #     self.setSpeed(10, axis=a)

    #     self.homed[a] = True  # update class homed status
    #     self.log.info("Homing complete.")

    # blocking call to relative move an axis the specified distance at speed (in mm/sec)
    # pylint: disable=too-many-arguments
    def relMove(self, mm=None, cnts=None, speed=None, acceleration=None, axis="D"):
        a = convertAxis(axis)  # check that the axis is valid
        old_speed = None
        old_acceleration = None
        if speed is not None:
            old_speed = self.getSpeed(axis=a)
            self.setSpeed(speed, axis=a)
        if acceleration is not None:
            old_acceleration = self.getAcceleration(axis=a)
            self.setAcceleration(acceleration, axis=a)
        if mm is not None:
            cnts = self.mmToCnts(mm, axis=a)
        if cnts is not None:
            start_position = self.getPosition(axis=a)
            self.log.info("Move axis %s to relative position %s", a, cnts)
            self.send("PR{}={}".format(a, cnts))
            self.send("BG{}".format(a))
            self.waitForMotionComplete(start_position + cnts, axis=a)
        if speed is not None:
            self.setSpeed(old_speed, axis=a)
        if acceleration is not None:
            self.setAcceleration(old_acceleration, axis=a)
        return self.getPosition(axis=a)

    # blocking call to move specified axis to absolute position at speed (in mm/sec)
    # pylint: disable=too-many-arguments
    def absMove(
        self,
        mm=None,
        cnts=None,
        speed=None,
        acceleration=None,
        wait_for_settling=True,
        axis="D",
    ):
        a = convertAxis(axis)
        if not self.homed[a]:
            msg = "Must home before using absolute movements!"
            self.log.critical(msg)
            sys.exit(msg)
        old_speed = None
        old_acceleration = None
        if speed is not None:
            old_speed = self.getSpeed(axis=a)
            self.setSpeed(speed, axis=a)
        if acceleration is not None:
            old_acceleration = self.getAcceleration(axis=a)
            self.setAcceleration(acceleration, axis=a)
        if mm is not None:
            cnts = self.mmToCnts(mm, axis=a)
        if cnts is not None:
            self.log.info("Move axis %s to absolute position %s", a, cnts)
            self.send("PA{}={}".format(a, cnts))
            self.send("BG{}".format(a))
            self.waitForMotionComplete(cnts, wait_for_settling=wait_for_settling, axis=a)
        if speed is not None:
            self.setSpeed(old_speed, axis=a)
        if acceleration is not None:
            self.setAcceleration(old_acceleration, axis=a)
        return self.getPosition(axis=a)

    # nonbocking call that start the axis moving at a specified speed.
    def startJog(self, speed=None, axis="D"):
        a = convertAxis(axis)
        if not self.jogging[a]:
            self.pre_jog_speed[a] = self.getSpeed(
                axis=a
            )  # save the speed before jogging begins
        self.jogging[a] = True
        self.log.info("Start jog on axis %s at speed %s mm/sec", a, speed)
        self.send("JG{}={}".format(a, speed * self.ctspmm[a]))
        self.send("BG{}".format(a))

    # nonbocking call that stops the motion of the stage.
    def stopJog(self, axis="D"):
        a = convertAxis(axis)
        self.log.info("Stop jog on axis %s", a)
        self.send("ST{}".format(a))
        self.jogging[a] = False
        self.setSpeed(self.pre_jog_speed[a])

    # block execution until the encoder reading reaches target.
    # Also notifys all position data
    def waitForMotionComplete(self, cnts, wait_for_settling=True, axis="D"):
        a = convertAxis(axis)
        start_time = time.time()
        last_position = self.getPosition(notify=False, axis=a)  # save the last position
        self.data["{}{}".format(a, self.move_num)] = []
        self.data["{}{}".format(a, self.move_num)].append(
            {
                "time": time.time(),
                "axis": a,
                "position": last_position,
                "error_window": -1,
            }
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
                    f"{a},{self.cntsToMm(self.getPosition(notify=False, axis=a))}\n",
                )
            time.sleep(0.001)
            last_position = self.getPosition(notify=False, axis=a)
            upper, lower = self.checkLimits(axis=a)
            if (lower and cnts < last_position) or (upper and cnts > last_position):
                self.log.info("Limit switch triggered")
                self.g.GMotionComplete(a)
                return
            self.data["{}{}".format(a, self.move_num)].append(
                {
                    "time": time.time(),
                    "axis": a,
                    "position": last_position,
                    "error_window": -1,
                }
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
                        f"{a},{self.cntsToMm(self.getPosition(notify=False, axis=a))}\n",
                    )
                time.sleep(0.001)
                last_position = self.getPosition(notify=False, axis=a)
                if any(self.checkLimits(axis=a)):
                    self.log.info("Limit switch triggered")
                    self.g.GMotionComplete(a)
                    return
                self.data["{}{}".format(a, self.move_num)].append(
                    {
                        "time": time.time(),
                        "axis": a,
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
                        "%s motor didn't reach position. Got to %s but needed %s",
                        a,
                        last_position,
                        cnts,
                    )
                    self.error_window = 1
                    break
        else:
            self.g.GMotionComplete(a)
        self.error_window = 1
        self.data["{}{}".format(a, self.move_num)].append(
            {
                "time": time.time(),
                "axis": a,
                "position": last_position,
                "error_window": -1,
            }
        )
        self.data["{}{}".format(a, self.move_num)].append(
            {"duration": time.time() - start_time}
        )
        self.move_num = self.move_num + 1

    # save motion data to a file
    # def saveMotionData(self, filename=None):
    #     # save the coefficients for this run
    #     for coeff in ("KP", "KI", "KD", "IL"):
    #         response = self.send("{} ?,?,?".format(coeff))
    #         response = response.replace(",", "")
    #         response = response.split()
    #         self.data["{}C".format(coeff)] = response[
    #             0
    #         ]  # get C axis which will be at index 2
    #     if filename is None:
    #         filename = "galil_data_P={}_I={}_D={}_IL={}.txt".format(
    #             self.data["KPC"], self.data["KIC"], self.data["KDC"], self.data["ILC"]
    #         )
    #     filename = cleanFileName(filename)
    #     with open(filename, "w") as outfile:
    #         json.dump(self.data, outfile)

    # end connection
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
