import sys
import time
import atexit
import logging
import threading
from pathlib import Path
from datetime import datetime

from printer_server.threading_wrapper import Thread
from printer_server.logging_handler import dummy_log
from printer_server.async_file_handler import async_file_hander
from printer_server.drivers.generic_drivers import BPStageDriver, FocusStageDriver, XYStageDriver

class Galil_dummy(BPStageDriver, FocusStageDriver, XYStageDriver):
    @dummy_log
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.movement_log = None
        self.config_dict = config_dict

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
        self.calibration_position = config_dict["calibration_position"]
        self.bottom_position = config_dict["bottom_position"]
        self.top_position = config_dict["top_position"]
        self.tolerence = config_dict["axes_tolerance"]

        self.movement_log_times = []
        self.movement_log_array = []

        self.homed = {}
        self.jogging = {}
        self.pre_jog_speed = {}
        self.pre_jog_acceleration = {}
        self.error_window = {}
        self.monitoring_window = {}
        self.logging_move_status = {}
        self.current_position = {}
        for a in self.axes:
            self.homed[a] = False
            self.jogging[a] = False
            self.pre_jog_speed[a] = 0
            self.pre_jog_acceleration[a] = 0
            self.error_window[a] = self.tolerence[a] * self.ctspmm[a] / 1000
            self.monitoring_window[a] = self.error_window[a] * 100
            self.logging_move_status[a] = -1
            self.current_position[a] = 0

        self.connected = None
        self.initialized = None

    # @dummy_log
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

    # @dummy_log
    def convertAxis(self, axis=None):
        """Return converted axis name (eg. maps X,Y,Z to A,B,C)"""
        if axis is None:
            axis = self.default_axis
        for i in range(len(self.axes)):
            if axis in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
            if axis.upper() in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
        raise ValueError("Invalid axis supplied")

    # @dummy_log
    def getCommonName(self, axis):
        if axis is None:
            axis = self.default_axis
        for i in range(len(self.axes)):
            if axis in (self.axes[i], self.axes_common_names[i]):
                return self.axes_common_names[i]
            if axis.upper() in (self.axes[i], self.axes_common_names[i]):
                return self.axes_common_names[i]
        raise ValueError("Invalid axis supplied")

    # @dummy_log
    def getDefaultSpeed(self, axis=None):
        a = self.convertAxis(axis)
        return self.default_speed[a]

    # @dummy_log
    def getDefaultAcceleration(self, axis=None):
        a = self.convertAxis(axis)
        return self.default_acceleration[a]

    @dummy_log
    def initialize(self):
        for axis in self.axes:
            self.motorOn(axis)

    @dummy_log
    def goToBPcalibration(self):
        self.absMove(mm=self.calibration_position, axis="Build Platform")
        self.current_position[self.convertAxis("Build Platform")] = self.calibration_position
        return self.getPosition(in_mm=True)

    @dummy_log
    def goToBPmax(self):
        self.absMove(mm=self.top_position, axis="Build Platform")
        self.current_position[self.convertAxis("Build Platform")] = self.top_position
        return self.getPosition(in_mm=True)

    @dummy_log
    def goToBPmin(self):
        self.absMove(mm=self.bottom_position, axis="Build Platform")
        self.current_position[self.convertAxis("Build Platform")] = self.bottom_position
        return self.getPosition(in_mm=True)

    @dummy_log
    def connect(self, shutdown):
        """Find the first Galil controller and connect to it."""
        if self.connected is None:
            self.connected = False
            if self.config_dict["address"] == "auto":
                self.log.info("Searching for %s controller...", self.controller_name)
                available = {"dummy_address": self.controller_name}
                self.address = None
                for address in sorted(available.keys()):
                    if self.controller_name in available[address]:
                        self.address = "dummy_address"
                        self.controller_name = available[address]
                        self.log.debug("Found %s at %s", available[address], self.address)
                        return self._connect(shutdown)
                msg = f"Galil controller not found! ({self.controller_name})"
                self.log.critical(msg)
                return False
            else:
                self.address = self.config_dict["address"]
                self.controller_name = self.config_dict["controller_name"]
                return self._connect(shutdown)
        else:
            while self.connected is False:
                time.sleep(0.1)

    def _connect(self, shutdown):
        self.log.info("Connecting to %s at %s", self.controller_name, self.address)
        self.log.debug("GInfo returned: dummy_info")
        self.connected = True
        self.thread_running = True
        self.thread.start()
        atexit.register(self.disconnect)
        self.log.info("Connected to Galil controller")
        self.shutdown = shutdown
        return True

    @dummy_log
    def disconnect(self):
        """Disconnect form the Galil controller."""
        if self.connected is not None and self.connected is not False:
            self.thread_running = False
            try:
                self.thread.join()
            except RuntimeError:
                pass
            self.thread = Thread(self.log, name="galil_loop_thread", target=self.loop)
            self.thread.daemon = True
            self.connected = None
            self.initialized = None
            self.log.info("Disconnected from Galil controller (%s)", self.controller_name)

    # @dummy_log
    def write_to_disk(self, *args):
        """Write data to disk using the async file handler class.

        Log location must be set for data to be saved.
        """
        ts = "%Y-%m-%d %H:%M:%S.%f"
        async_file_hander.write(self.movement_log, datetime.now().strftime(ts) + ",")
        async_file_hander.write(self.movement_log, ",".join(map(str, args)) + "\n")

    # @dummy_log
    def mmToCnts(self, mm, axis=None):
        """Convert mm to counts for the specified axis."""
        return int(mm * self.ctspmm[self.convertAxis(axis)])

    # @dummy_log
    def cntsToMm(self, counts, axis=None):
        """Convert counts to mm for the specified axis."""
        return counts / self.ctspmm[self.convertAxis(axis)]

    # @dummy_log
    def send(self, command, notify=True):
        """Send a command to the controller.

        If an error is returned, request and also return more
        information about the error.
        """
        with self.sendLock:
            if notify:
                self.log.debug("Sent : '%s'", command)
            response = "dummy_response"
            response = "".join(response)
            if notify and response != "":
                self.log.debug("Reply: '%s'", response)
            return response

    # @dummy_log
    def checkLimits(self, axis=None):
        """Return a tuple the state of the limit switches for the
        specified axis.
        """
        a = self.convertAxis(axis)
        lf = "0.0000"
        lr = "0.0000"
        return bool(lf == "0.0000"), bool(lr == "0.0000")

    # @dummy_log
    def getPosition(self, in_mm, axis=None, notify=True):
        """Return the position of the specified encoder."""
        pos = self.current_position[self.convertAxis(axis)]
        if not in_mm:
            return int(pos)
        else:
            return self.cntsToMm(int(pos), axis=axis)

    @dummy_log
    def motorOn(self, axis=None):
        """Turn on the specified axis."""
        pass

    @dummy_log
    def motorOff(self, axis=None):
        """Turn off the specified axis."""
        a = self.convertAxis(axis)
        self.log.warning("Axis %s motor turned off. It may sink due to gravity.", a)

    # @dummy_log
    def getAcceleration(self, axis=None):
        """Return the acceleration of the specified axis (mm/sec^2)."""
        a = self.convertAxis(axis)
        acc = 1000
        return int(acc) / self.ctspmm[a]

    @dummy_log
    def setAcceleration(self, acceleration, axis=None):
        """Set the acceleration for the specified axis (mm/sec^2)."""
        a = self.convertAxis(axis)
        pass

    # @dummy_log
    def getSpeed(self, axis=None):
        """Return the speed for the specified axis (mm/sec)."""
        a = self.convertAxis(axis)
        speed = 1000
        return int(speed) / self.ctspmm[a]

    @dummy_log
    def setSpeed(self, speed, axis=None):
        """Set the speed for the specified axis (mm/sec)."""
        a = self.convertAxis(axis)
        pass

    @dummy_log
    def home(self):
        """Run the homing routine.

        The homing routine begins by jogging up until the limit switch
        is triggered, then runs the built in "HM" routine and waits for
        motion to complete.
        """
        if "DMC31010" in self.controller_name:
            self.log.info("Start homing...")
            a = self.convertAxis()
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
            self.current_position[a] = 0.0

        elif "DMC4040" in self.controller_name:
            self.log.info("Start homing...")
            self.send("XQ #HMA,0")
            self.send("XQ #HMB,1")
            self.send("XQ #HMC,2")
            self.send("XQ #HMD,3")

            for a in self.axes:
                self.motionPlanningComplete(axis=a)
                self.homed[a] = True  # update class homed status
                self.current_position[a] = 0.0
            self.log.info("Homing complete.")

        for a in self.axes:
            self.setSpeed(self.getDefaultSpeed(a), axis=a)
            self.setAcceleration(self.getDefaultAcceleration(a), axis=a)

    ################################# Parent class functions #######################################

    @dummy_log
    def getXYPosition(self, axis=None, notify=True):
        return self.getPosition(in_mm=True, axis=axis)

    @dummy_log
    def absMoveXY(self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        self.absMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)

    @dummy_log
    def relMoveXY(self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        self.relMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)

    @dummy_log
    def startXYJog(self, speed=None, acceleration=None, axis=None):
        self.startJog(speed=speed, acceleration=acceleration, axis=axis)

    @dummy_log
    def stopXYJog(self, axis=None):
        self.stopJog(axis=axis)

    @dummy_log
    def getFocusPosition(self, notify=True):
        return self.getPosition(in_mm=True, axis="Focus")

    @dummy_log
    def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.absMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Focus")

    @dummy_log
    def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.relMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Focus")

    @dummy_log
    def startFocusJog(self, speed=None, acceleration=None):
        self.startJog(speed=speed, acceleration=acceleration, axis="Focus")

    @dummy_log
    def stopFocusJog(self):
        self.stopJog(axis="Focus")

    @dummy_log
    def getBPPosition(self, notify=True):
        return self.getPosition(in_mm=True, axis="Build Platform")

    @dummy_log
    def absMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.absMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Build Platform")

    @dummy_log
    def relMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.relMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Build Platform")

    @dummy_log
    def startBPJog(self, speed=None, acceleration=None):
        self.startJog(speed=speed, acceleration=acceleration, axis="Build Platform")

    @dummy_log
    def stopBPJog(self):
        self.stopJog(axis="Build Platform")

        ################################# End parent class functions #######################################

    @dummy_log
    def relMove(self, mm=None, cnts=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        """Perform a relative movement."""
        a = self.convertAxis(axis)
        self.current_position[a] += mm
        self.log.info("Move axis %s relative by %s mm or %s counts", a, mm, cnts)
        if speed is not None:
            self.setSpeed(speed, axis=a)
        if acceleration is not None:
            self.setAcceleration(acceleration, axis=a)
        return self.getPosition(in_mm=True, axis=a)

    @dummy_log
    def absMove(self, mm=None, cnts=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        """Perform an absolute movement."""
        a = self.convertAxis(axis)
        self.current_position[a] = mm
        if not self.homed[a]:
            msg = "Must home before using absolute movements!"
            self.log.error(msg)
            return self.getPosition(in_mm=True, axis=a)
        self.log.info("Move axis %s to absolute position %s mm or %s counts", a, mm, cnts)
        if speed is not None:
            self.setSpeed(speed, axis=a)
        if acceleration is not None:
            self.setAcceleration(acceleration, axis=a)
        return self.getPosition(in_mm=True, axis=a)

    @dummy_log
    def startJog(self, speed=None, acceleration=None, axis=None):
        """Start a jog, non-blocking."""
        a = self.convertAxis(axis)
        self.log.info("Start jog on axis %s at speed %s mm/sec", a, speed)
        self.setSpeed(speed, axis=a)
        self.setAcceleration(acceleration, axis=a)

    @dummy_log
    def stopJog(self, axis=None):
        """Stop a jog, non-blocking."""
        a = self.convertAxis(axis)
        self.log.info("Stop jog on axis %s", a)

    @dummy_log
    def motionPlanningComplete(self, axis=None):
        """Check if motion planning is complete."""
        pass

    @dummy_log
    def waitForMotionComplete(self, cnts, wait_for_settling=True, axis=None):
        """Blocks execution until the encoder reaches the target value."""
        pass

    @dummy_log
    def setup_log_file(self, filename):
        """Set the log file."""
        if self.movement_log is None and filename is not None:
            self.movement_log = str(Path(filename) / "galil_movement_data.csv")
        elif self.movement_log is not None and filename is None:
            self.movement_log = None

    @dummy_log
    def logging_start(self):
        """Starts collecting position data."""
        pass

    @dummy_log
    def logging_stop(self):
        """Stops collecting position data."""
        pass

    @dummy_log
    def loop(self):
        """Main loop to update positions and log data."""
        while self.thread_running:
            for a in self.axes:
                self.current_position[a] = self.getPosition(in_mm=False, notify=False, axis=a)
            time.sleep(0.01)

    @dummy_log
    def downloadProgram(self, filename):
        """Download a DMC file to the Galil controller."""
        self.log.info("Downloading '%s' to controller...", filename)

    @dummy_log
    def interactiveMode(self):
        """Start interactive mode."""
        if not self.connected:
            msg = "Must be connected to Galil controller to run interactive mode"
            self.log.critical(msg)
            sys.exit(msg)
        try:
            while True:
                cmd = input("Give Galil a command>> ").strip()
                self.log.info("Command given: %s", cmd)
                print(self.send(cmd.upper()))
        except KeyboardInterrupt:
            self.log.info("Exited by KeyboardInterrupt")

if __name__ == "__main__":
    g = Galil_dummy(log_level=logging.DEBUG)
    g.connect(exit)
    g.interactiveMode()
