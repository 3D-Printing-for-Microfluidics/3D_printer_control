"""Galil control module."""
import sys
import time
import atexit
import logging
from datetime import datetime
import gclib
from printer_server.async_file_handler import async_file_hander


class Galil:
    def __init__(
        self,
        config_dict=None,
        log_level=logging.DEBUG,
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.movement_log = None

        self.gclib_error = gclib.GclibError

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

        self.homed = {}
        self.jogging = {}
        self.pre_jog_speed = {}
        self.pre_jog_acceleration = {}
        self.error_window = {}
        self.monitoring_window = {}
        for a in self.axes:
            self.homed[a] = False
            self.jogging[a] = False
            self.pre_jog_speed[a] = 0
            self.pre_jog_acceleration[a] = 0
            self.error_window[a] = self.tolerence[a] * self.ctspmm[a] / 1000
            self.monitoring_window[a] = self.error_window[a] * 100

        self.connected = False

        self.g = gclib.py()
        atexit.register(self.disconnect)

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
        axis = axis.upper()
        for i in range(len(self.axes)):
            if axis in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
        raise ValueError("Invalid axis supplied")

    def initialize(self):
        for axis in self.axes:
            self.motorOn(axis)

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
                self.g.GOpen(f"{self.address} --direct")
                self.log.debug("GInfo returned: %s", self.g.GInfo())
                self.connected = True
                return
        msg = f"{self.controller_name} not found."
        self.log.critical(msg)
        sys.exit(msg)

    def write_to_disk(self, *args):
        """Write data to disk using the async file handler class.

        Log location must be set for data to be saved.
        """
        if self.movement_log is not None:
            ts = "%Y-%m-%d %H:%M:%S.%f"
            async_file_hander.write(self.movement_log, datetime.now().strftime(ts) + ",")
            async_file_hander.write(self.movement_log, ",".join(map(str, args)) + "\n")

    def mmToCnts(self, mm, axis=None):
        """Convert mm to counts for the specified axis."""
        return int(mm * self.ctspmm[self.convertAxis(axis)])

    def cntsToMm(self, counts, axis=None):
        """Convert counts to mm for the specified axis."""
        return counts / self.ctspmm[self.convertAxis(axis)]

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

    def checkLimits(self, axis=None):
        """Return a tuple the state of the limit switches for the
        specified axis.
        """
        a = self.convertAxis(axis)
        lf = self.send(f"MG _LF{a}", notify=False)
        lr = self.send(f"MG _LR{a}", notify=False)
        return bool(lf == "0.0000"), bool(lr == "0.0000")

    def getPosition(self, axis=None, notify=True):
        """Return the position of the specified encoder."""
        pos = self.send(f"TP{self.convertAxis(axis)}", notify=notify)
        return int(pos)

    def motorOn(self, axis=None):
        """Turn on the specified axis."""
        self.send(f"SH{self.convertAxis(axis)}")

    def motorOff(self, axis=None):
        """Turn off the specified axis."""
        a = self.convertAxis(axis)
        self.log.warning("Axis %s motor turned off. It may sink due to gravity.", a)
        self.send(f"MO{a}")

    def getAcceleration(self, axis=None):
        """Return the acceleration of the specified axis (mm/sec^2)."""
        a = self.convertAxis(axis)
        response = self.send("AC ?,?,?,?", notify=False)
        acc = self.parseResponseString(response, a)
        return int(acc) / self.ctspmm[a]

    def setAcceleration(self, acceleration, axis=None):
        """Set the acceleration for the specified axis (mm/sec^2)."""
        a = self.convertAxis(axis)
        self.send(f"AC{a}={acceleration * self.ctspmm[a]}")
        self.send(f"DC{a}={acceleration * self.ctspmm[a]}")

    def getSpeed(self, axis=None):
        """Return the speed for the specified axis (mm/sec)."""
        a = self.convertAxis(axis)
        response = self.send("SP ?,?,?,?", notify=False)
        speed = self.parseResponseString(response, a)
        return int(speed) / self.ctspmm[a]

    def setSpeed(self, speed, axis=None):
        """Set the speed for the specified axis (mm/sec)."""
        a = self.convertAxis(axis)
        self.send(f"SP{a}={speed * self.ctspmm[a]}")

    def home(self, axis=None):
        """Run the homing routine.

        The homing routine begins by jogging up until the limit switch
        is triggered, then runs the built in "HM" routine and waits for
        motion to complete.
        """
        if "DMC31010" in self.controller_name:
            self.log.info("Start homing...")
            a = self.convertAxis(axis)
            self.setSpeed(10)
            self.motorOn()
            self.startJog(speed=-15, acceleration=50)
            self.g.GMotionComplete(a)
            self.stopJog()
            self.motorOn()
            self.send("HM")
            self.send("BGA")
            self.waitForMotionComplete(0)
            self.g.GMotionComplete(a)
            self.homed[a] = True
            self.log.info("Homing complete.")

        elif "DMC4040" in self.controller_name:
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

    # pylint: disable=too-many-arguments
    def relMove(self, mm=None, cnts=None, speed=None, acceleration=None, axis=None):
        """Perform a relative movement.

        Blocks execution until movement is complete. All units are in mm
        and mm/sec(^2).
        """
        a = self.convertAxis(axis)  # check that the axis is valid
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
            self.send(f"PR{a}={cnts}")
            self.send(f"BG{a}")
            self.waitForMotionComplete(start_position + cnts, axis=a)
        if speed is not None:
            self.setSpeed(old_speed, axis=a)
        if acceleration is not None:
            self.setAcceleration(old_acceleration, axis=a)
        return self.getPosition(axis=a)

    # pylint: disable=too-many-arguments
    def absMove(
        self,
        mm=None,
        cnts=None,
        speed=None,
        acceleration=None,
        wait_for_settling=True,
        axis=None,
    ):
        """Perform an absolute movement.

        Blocks execution until movement is complete. All units are in mm
        and mm/sec(^2). wait_for_settling determines how precise
        the movement has to be.
        """
        a = self.convertAxis(axis)
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
            self.send(f"PA{a}={cnts}")
            self.send(f"BG{a}")
            self.waitForMotionComplete(cnts, wait_for_settling=wait_for_settling, axis=a)
        if speed is not None:
            self.setSpeed(old_speed, axis=a)
        if acceleration is not None:
            self.setAcceleration(old_acceleration, axis=a)
        return self.getPosition(axis=a)

    def startJog(self, speed=None, acceleration=None, axis=None):
        """Start a jog, non-blocking."""
        a = self.convertAxis(axis)
        if not self.jogging[a]:
            self.pre_jog_speed[a] = self.getSpeed(
                axis=a
            )  # save the speed before jogging begins
            self.pre_jog_acceleration[a] = self.getAcceleration(
                axis=a
            )  # save the speed before jogging begins
        self.jogging[a] = True

        self.log.info("Start jog on axis %s at speed %s mm/sec", a, speed)
        self.setAcceleration(acceleration)
        self.send(f"JG{a}={speed * self.ctspmm[a]}")
        self.send(f"BG{a}")

    def stopJog(self, axis=None):
        """Stop a jog, non-blocking."""
        a = self.convertAxis(axis)
        self.log.info("Stop jog on axis %s", a)
        self.send(f"ST{a}")
        self.jogging[a] = False
        self.setSpeed(self.pre_jog_speed[a])
        self.setAcceleration(self.pre_jog_acceleration[a])

    def waitForMotionComplete(self, cnts, wait_for_settling=True, axis=None):
        """Blocks execution until the encoder reaches the target value
        and saves motion data as it goes.
        """
        a = self.convertAxis(axis)
        last_position = self.getPosition(notify=False, axis=a)  # save the last position
        self.write_to_disk(self.cntsToMm(last_position, axis=a))
        counter = 0
        time_count = 0
        # wait until we are within 10 um of target
        while not (
            int(cnts - self.monitoring_window[a])
            <= last_position
            <= int(cnts + self.monitoring_window[a])
        ):
            time.sleep(0.001)
            last_position = self.getPosition(notify=False, axis=a)
            self.write_to_disk(self.cntsToMm(last_position, axis=a))
            upper, lower = self.checkLimits(axis=a)
            if (lower and cnts < last_position) or (upper and cnts > last_position):
                self.log.info("Limit switch triggered")
                self.g.GMotionComplete(a)
                return
        if wait_for_settling:
            # only proceed when 10 good consecutive counts have been read
            error = self.error_window[a]
            while counter <= 5:
                time.sleep(0.001)
                last_position = self.getPosition(notify=False, axis=a)
                self.write_to_disk(self.cntsToMm(last_position, axis=a))
                if any(self.checkLimits(axis=a)):
                    self.log.info("Limit switch triggered")
                    self.g.GMotionComplete(a)
                    return
                if int(cnts - error) <= last_position <= int(cnts + error):
                    counter += 1
                else:
                    counter = 0
                time_count += 1
                # timeout for collecting data, motor won't reach position
                if time_count == 100:
                    error = error * 2
                if time_count >= 5000:
                    self.log.warning(
                        "Z motor didn't reach position. Got to %s but needed %s",
                        last_position,
                        cnts,
                    )
                    break
        else:
            self.g.GMotionComplete(a)
        self.write_to_disk(
            self.cntsToMm(self.getPosition(notify=False, axis=a), axis=a), "move_complete"
        )

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
