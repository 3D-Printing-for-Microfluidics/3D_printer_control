"""Galil control module."""
import sys
import threading
import time
import atexit
import logging
from datetime import datetime
import gclib
from printer_server.async_file_handler import async_file_hander
from printer_server.threading_wrapper import Thread


class Galil:
    def __init__(
        self,
        config_dict=None,
        log_level=logging.DEBUG,
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.movement_log = None
        self.config_dict = config_dict

        self.gclib_error = gclib.GclibError
        self.sendLock = threading.Lock()

        self.thread = Thread(self.log, name="galil_loop_thread", target=self.loop)
        self.thread.daemon = True
        self.thread_running = False
        self.logging_running = False

        self.controller_name = config_dict["controller_name"]
        self.default_axis = config_dict["default_axis"]
        self.axes = config_dict["axes"]
        self.axes_common_names = config_dict["axes_common_names"]
        self.max_travel_mm = config_dict["axes_travel"]
        self.ctspmm = config_dict["axes_ctspmm"]
        self.default_speed = config_dict["axes_speed"]
        self.default_acceleration = config_dict["axes_acceleration"]
        self.calibration_position = self.cntsToMm(config_dict["calibration_position"], axis="Build Platform")
        self.bottom_position = self.cntsToMm(config_dict["bottom_position"], axis="Build Platform")
        self.top_position = self.cntsToMm(config_dict["top_position"], axis="Build Platform")
        self.tolerence = config_dict["axes_tolerance"]

        self.homed = {}
        self.jogging = {}
        self.pre_jog_speed = {}
        self.pre_jog_acceleration = {}
        self.error_window = {}
        self.monitoring_window = {}
        self.logging_move_status = {}
        self.current_position = {}
        # -1 = Not moving
        # 0 = Moving
        # 1 = Profiled Motion Complete
        # 2 = Settling Complete
        # 3 = Error Settling
        for a in self.axes:
            self.homed[a] = False
            self.jogging[a] = False
            self.pre_jog_speed[a] = 0
            self.pre_jog_acceleration[a] = 0
            self.error_window[a] = self.tolerence[a] * self.ctspmm[a] / 1000
            self.monitoring_window[a] = self.error_window[a] * 100
            self.logging_move_status[a] = -1
            self.current_position[a] = 0

        self.connected = False

        self.g = gclib.py()

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

    def getCommonName(self, axis):
        if axis is None:
            axis = self.default_axis
        for i in range(len(self.axes)):
            if axis in (self.axes[i], self.axes_common_names[i]):
                return self.axes_common_names[i]
            if axis.upper() in (self.axes[i], self.axes_common_names[i]):
                return self.axes_common_names[i]
        raise ValueError("Invalid axis supplied")

    def getDefaultSpeed(self, axis=None):
        a = self.convertAxis(axis)
        return self.default_speed[a]

    def getDefaultAcceleration(self, axis=None):
        a = self.convertAxis(axis)
        return self.default_acceleration[a]

    def initialize(self):
        for axis in self.axes:
            self.motorOn(axis)

    def goToZcalibration(self):
        self.absMove(speed=self.getDefaultSpeed("Build Platform"), mm=self.calibration_position, axis="Build Platform")
        return self.getPosition(in_mm=True)

    def goToZmax(self):
        self.absMove(speed=self.getDefaultSpeed("Build Platform"), mm=self.top_position, axis="Build Platform")
        return self.getPosition(in_mm=True)

    def goToZmin(self):
        self.absMove(speed=self.getDefaultSpeed("Build Platform"), mm=self.bottom_position, axis="Build Platform")
        return self.getPosition(in_mm=True)

    def connect(self, shutdown):
        """Find the first Galil controller and connect to it."""
        self.log.info("Searching for %s controller...", self.controller_name)
        available = self.g.GAddresses()
        self.address = None
        for address in sorted(available.keys()):
            if self.controller_name in available[address]:
                self.address = address.strip("()").strip("-d")
                self.controller_name = available[address]
                self.log.debug("Found %s at %s", available[address], self.address)
                self.log.info(
                    "Connecting to %s at %s", self.controller_name, self.address
                )
                self.g.GOpen(f"{self.address} --direct")
                self.log.debug("GInfo returned: %s", self.g.GInfo())
                self.connected = True
                self.thread_running = True
                self.thread.start()
                atexit.register(self.disconnect)
                self.log.info("Connected to Galil controller")
                self.shutdown = shutdown
                return True
        msg = f"Galil controller not found! ({self.controller_name})"
        self.log.critical(msg)
        return False

    def disconnect(self):
        """Disconnect form the Galil controller."""
        if self.connected is not False:
            self.thread_running = False
            try:
                self.thread.join()
            except RuntimeError:
                pass
            self.thread = Thread(self.log, name="galil_loop_thread", target=self.loop)
            self.thread.daemon = True
            try:
                self.connected = False
                self.g.GClose()
                self.log.info("Disconnected from Galil controller (%s)", self.controller_name)
            except self.gclib_error as e:
                self.log.error("Unexpected GclibError on disconnect: %s", e)


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
        with self.sendLock:
            if notify:
                self.log.debug("Sent : '%s'", command)
            try:
                response = self.g.GCommand(command)
                response = "".join(response)
                if notify and response != "":
                    self.log.debug("Reply: '%s'", response)
                return response
            except self.gclib_error as error:
                if str(error) == "device timed out":
                    msg = "Galil controller timed out!"
                    self.log.critical(msg)
                    # Thread(self.log, self.shutdown, kwargs={"is_critical": True}).start()
                    self.shutdown(is_critical = True)
                    sys.exit(msg)
                else:
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

    def getPosition(self, in_mm, axis=None, notify=True):
        """Return the position of the specified encoder."""
        pos = self.send(f"TP{self.convertAxis(axis)}", notify=notify)
        if not in_mm:
            return int(pos)
        else:
            return self.cntsToMm(int(pos), axis=axis)

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
            self.motionPlanningComplete(axis=a)
            self.stopJog()
            self.motorOn()
            self.send("HM")
            self.send("BGA")
            self.waitForMotionComplete(0)
            self.motionPlanningComplete(axis=a)
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
                self.motionPlanningComplete(axis=a)
                self.homed[a] = True  # update class homed status
            self.log.info("Homing complete.")

    # pylint: disable=too-many-arguments
    def relMove(self, mm=None, cnts=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
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
            start_position = self.getPosition(in_mm=False, axis=a)
            self.log.info("Move axis %s to relative position %s", a, cnts)
            self.send(f"PR{a}={cnts}")
            self.send(f"BG{a}")
            self.logging_move_status[a] = 0
            self.waitForMotionComplete(start_position + cnts, wait_for_settling=wait_for_settling, axis=a)
        if speed is not None:
            self.setSpeed(old_speed, axis=a)
        if acceleration is not None:
            self.setAcceleration(old_acceleration, axis=a)
        return self.getPosition(in_mm=True, axis=a)

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
            self.log.error(msg)
            return self.getPosition(in_mm=True, axis=a)
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
            self.logging_move_status[a] = 0
            self.waitForMotionComplete(cnts, wait_for_settling=wait_for_settling, axis=a)
        if speed is not None:
            self.setSpeed(old_speed, axis=a)
        if acceleration is not None:
            self.setAcceleration(old_acceleration, axis=a)
        return self.getPosition(in_mm=True, axis=a)

    def startJog(self, speed=None, acceleration=None, axis=None):
        """Start a jog, non-blocking."""
        a = self.convertAxis(axis)
        if not self.jogging[a]:
            self.pre_jog_speed[a] = self.getSpeed(
                axis=a
            )  # save the speed before jogging begins
            self.pre_jog_acceleration[a] = self.getAcceleration(
                axis=a
            )  # save the acceleration before jogging begins
        self.jogging[a] = True

        self.setAcceleration(acceleration)
        self.log.info("Start jog on axis %s at speed %s mm/sec", a, speed)
        self.send(f"JG{a}={speed * self.ctspmm[a]}")
        self.send(f"BG{a}")
        self.logging_move_status[a] = 0

    def stopJog(self, axis=None):
        """Stop a jog, non-blocking."""
        a = self.convertAxis(axis)
        self.log.info("Stop jog on axis %s", a)
        self.send(f"ST{a}")
        self.logging_move_status[a] = -1
        self.jogging[a] = False
        self.setSpeed(self.pre_jog_speed[a])
        self.setAcceleration(self.pre_jog_acceleration[a])

    def motionPlanningComplete(self, axis=None):
        a = self.convertAxis(axis)
        in_motion = float(self.send(f"MG _BG{a}", notify=False))
        while in_motion == 1.0:
            time.sleep(0.01)
            in_motion = float(self.send(f"MG _BG{a}", notify=False))

    def waitForMotionComplete(self, cnts, wait_for_settling=True, axis=None):
        """Blocks execution until the encoder reaches the target value
        and saves motion data as it goes.
        """
        a = self.convertAxis(axis)
        counter = 0
        time_count = 0
        limit_switch_triggered = False
        in_motion = float(self.send(f"MG _BG{a}", notify=False))
        while in_motion == 1.0:
            time.sleep(0.01)
            in_motion = float(self.send(f"MG _BG{a}", notify=False))
            upper, lower = self.checkLimits(axis=a)
            position = self.current_position[a]
            if (
                not limit_switch_triggered
                and (lower and cnts < position)
                or (upper and cnts > position)
            ):
                limit_switch_triggered = True
                wait_for_settling = False
                self.log.info("Axis %s limit switch triggered during motion", a)

        # self.logging_profile_complete = True
        self.logging_move_status[a] = 1
        if wait_for_settling:
            # only proceed when 10 good consecutive counts have been read
            error = self.error_window[a]
            while counter <= 5:
                time.sleep(0.01)
                position = self.current_position[a]
                if any(self.checkLimits(axis=a)):
                    self.log.info("Axis %s limit switch triggered during settling", a)
                    # self.logging_move_complete = True
                    self.logging_move_status[a] = 3
                    return
                if int(cnts - error) <= position <= int(cnts + error):
                    counter += 1
                else:
                    counter = 0
                time_count += 1
                # timeout for collecting data, motor won't reach position
                if time_count == 10:
                    error = error * 2
                if time_count >= 500:
                    self.log.warning(
                        "%s motor didn't reach position. Got to %s but needed %s",
                        a,
                        position,
                        cnts,
                    )
                    break
        # self.logging_move_complete = True
        self.logging_move_status[a] = 2

    def set_log_file(self, filename):
        """Set the log file."""
        self.movement_log = filename

    def logging_start(self):
        """
        Starts collecting position data
        """
        if not self.logging_running:
            self.logging_running = True
            self.log.info("Galil logging started")

    def logging_stop(self):
        """
        Stops collecting position data
        """

        if self.logging_running:
            self.logging_running = False
            self.log.info("Galil logging stopped")

    def loop(self):
        while self.thread_running:
            for a in self.axes:
                self.current_position[a] = self.getPosition(in_mm=False, notify=False, axis=a)
            if self.logging_running:
                tmp = ""
                for a in self.axes:
                    position = self.current_position[a]
                    tmp += f"{self.cntsToMm(position, axis=a)},"
                    tmp += f"{self.logging_move_status[a]},"
                    if self.logging_move_status[a] >= 2:
                        self.logging_move_status[a] = -1
                self.write_to_disk(tmp)
                time.sleep(0.01)

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


if __name__ == "__main__":
    g = Galil(log_level=logging.DEBUG)
    g.connect()
    g.interactiveMode()
