"""Galil control module."""
import sys
import threading
import time
import atexit
import logging
from pathlib import Path
from datetime import datetime
import gclib
from printer_server.async_file_handler import async_file_hander
from printer_server.threading_wrapper import Thread
from printer_server.drivers.generic_drivers import BPStageDriver, FocusStageDriver, XYStageDriver

# first_load = True
# if first_load:
#     first_load = False
#     print(f"Galil:")
#     print(f"\t{gclib.py().GAddresses()}")
#     print(f"\t")

class Galil(BPStageDriver, FocusStageDriver, XYStageDriver):
    def __init__(
        self,
        config_dict=None,
        log_level=logging.DEBUG,
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.movement_log = None
        self.config_dict = config_dict

        super().__init__()

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
        self.limits = config_dict["limits"]
        self.calibration_limits = config_dict["calibration_limits"]
        self.calibration_position = config_dict["calibration_position"]
        self.bottom_position = config_dict["bottom_position"]
        self.top_position = config_dict["top_position"]
        self.tolerence = config_dict["axes_tolerance_um"]

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

        self.connected = None

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

    def goToBPcalibration(self):
        self.absMove(mm=self.calibration_position, axis="Build Platform")
        return self.getPosition(in_mm=True)

    def goToBPtop(self):
        self.absMove(mm=self.top_position, axis="Build Platform")
        return self.getPosition(in_mm=True)

    def goToBPbottom(self):
        self.absMove(mm=self.bottom_position, axis="Build Platform")
        return self.getPosition(in_mm=True)

    def connect(self):
        """Find the first Galil controller and connect to it."""
        if self.connected is None:
            self.connected = False
            if self.config_dict["address"] == "auto":
                self.log.info("Searching for %s controller...", self.controller_name)
                available = self.g.GAddresses()
                self.address = None
                for address in sorted(available.keys()):
                    if self.controller_name in available[address]:
                        self.address = address.strip("()").strip("-d")
                        self.controller_name = available[address]
                        self.log.debug("Found %s at %s", available[address], self.address)
                        return self._connect()
                self.connected = None
                msg = f"Galil controller not found! ({self.controller_name})"
                self.log.error(msg)
                return False
            else:
                self.address = self.config_dict["address"]
                self.controller_name = self.config_dict["controller_name"]
                return self._connect()
        else:
            while self.connected is False:
                time.sleep(0.1)

    def _connect(self):
        self.log.info(
            "Connecting to %s at %s", self.controller_name, self.address
        )
        try:
            self.g.GOpen(f"{self.address} --direct")
            self.log.debug("GInfo returned: %s", self.g.GInfo())
            self.connected = True
            self.thread_running = True
            self.thread.start()
            atexit.register(self.disconnect)
            self.log.info("Connected to Galil controller")
            return True
        except self.gclib_error as ex:
            self.connected = None
            msg = f"Galil controller not found! ({self.controller_name}): {ex}"
            self.log.error(msg)
            return False

    def disconnect(self):
        """Disconnect form the Galil controller."""
        if self.connected is not None and self.connected is not False:
            self.thread_running = False
            try:
                self.thread.join()
                self.thread = Thread(self.log, name="galil_loop_thread", target=self.loop)
                self.thread.daemon = True

                for axis in self.axes:
                    self.motorOff(axis)
            except:
                pass

            try:
                self.connected = None
                self.g.GClose()
                self.log.info("Disconnected from Galil controller (%s)", self.controller_name)
            except self.gclib_error as ex:
                self.log.info("Unexpected GclibError on disconnect: %s", ex)


    def write_to_disk(self, *args):
        """Write data to disk using the async file handler class.

        Log location must be set for data to be saved.
        """
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
                    raise error
                else:
                    error_code = self.g.GCommand("TC 1")
                    if error_code not in ("", "0"):
                        error = error_code
                    self.log.error("Last command '%s' returned error '%s'", command, error)
                    return error
                
    def getSoftwareLimits(self, axis=None):
        a = self.convertAxis(axis)
        ll = self.cntsToMm(int(self.send(f"BL{a}=?")), axis=axis)
        ul = self.cntsToMm(int(self.send(f"FL{a}=?")), axis=axis)
        return (ll, ul)
    
    def setLowerLimit(self, limit, axis=None):
        a = self.convertAxis(axis)
        self.send(f"BL{a}={limit * self.ctspmm[a]}")

    def setUpperLimit(self, limit, axis=None):
        a = self.convertAxis(axis)
        self.send(f"FL{a}={limit * self.ctspmm[a]}")

    def checkLimits(self, axis=None):
        """Return a tuple the state of the limit switches for the
        specified axis.
        """
        a = self.convertAxis(axis)
        lf = self.send(f"MG _LF{a}", notify=False)
        lr = self.send(f"MG _LR{a}", notify=False)
        return bool(lf == "0.0000"), bool(lr == "0.0000")

    # def getPosition(self, in_mm, axis=None, notify=True):
    #     """Return the position of the specified encoder."""
    #     pos = self.send(f"TP{self.convertAxis(axis)}", notify=notify)
    #     if not in_mm:
    #         return int(pos)
    #     else:
    #         return self.cntsToMm(int(pos), axis=axis)
        
    def getPosition(self, in_mm, axis=None, notify=True):
        """Return the position of the specified encoder."""
        if type(axis) is not list:
            pos = self.send(f"TP{self.convertAxis(axis)}", notify=notify)
            if not in_mm:
                return int(pos)
            else:
                return self.cntsToMm(int(pos), axis=axis)
        else:
            parsed_axis = ""
            for a in axis:
                parsed_axis += self.convertAxis(a)
            
            pos_list = self.send(f"TP{parsed_axis}", notify=notify)
            pos = pos_list.split(",")
            ret_dict = {}
            for i, a in enumerate(axis):
                if not in_mm:
                    ret_dict[a] = int(pos[i])
                else:
                    ret_dict[a] = self.cntsToMm(int(pos[i]), axis=a)
            return ret_dict

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

        for a in self.axes:
            self.setSpeed(self.getDefaultSpeed(a), axis=a)
            self.setAcceleration(self.getDefaultAcceleration(a), axis=a)

    ################################# Parent class functions #######################################
            
    def getDefaultBPSpeed(self):
        return self.getDefaultSpeed("Build Platform")

    def getDefaultBPAcceleration(self):
        return self.getDefaultAcceleration("Build Platform")

    def getDefaultFocusSpeed(self):
        return self.getDefaultSpeed("Focus")

    def getDefaultFocusAcceleration(self):
        return self.getDefaultAcceleration("Focus")

    def getDefaultXYSpeed(self, axis=None):
        return self.getDefaultSpeed(axis)

    def getDefaultXYAcceleration(self, axis=None):
        return self.getDefaultAcceleration(axis)

    def getXYPosition(self, axis=None, notify=True):
        return self.getPosition(in_mm=True, axis=axis)

    def absMoveXY( self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        self.absMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)

    def relMoveXY(self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        self.relMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)

    def startXYJog(self, speed=None, acceleration=None, axis=None):
        self.startJog(speed=speed, acceleration=acceleration, axis=axis)

    def stopXYJog(self, axis=None):
        self.stopJog(axis=axis)

    def getXYLimits(self, axis=None):
        a = self.convertAxis(axis)
        sl = self.getSoftwareLimits(axis=a)
        if self.limits[a][0] is not None:
            ll = sl[0]
        else:
            ll = -self.max_travel_mm[a]/2
        if self.limits[a][1] is not None:  
            ul = sl[1]
        else:
            ul = self.max_travel_mm[a]/2
        return (ll,ul)
    
    def setXYLimits(self, limits=None, axis=None):
        a = self.convertAxis(axis)
        if limits is None:
            limits = self.limits[a]
        if limits[0] is not None:
            self.setLowerLimit(limits[0], axis=a)
        if limits[1] is not None:
            self.setUpperLimit(limits[1], axis=a)

    def getFocusPosition(self, notify=True):
        return self.getPosition(in_mm=True, axis="Focus")

    def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        if mm < self.getPosition(in_mm=True, axis="Focus"):
            self.absMove(mm=mm-0.1, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Focus")
        self.absMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Focus")

    def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.relMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Focus")

    def startFocusJog(self, speed=None, acceleration=None):
        self.startJog(speed=speed, acceleration=acceleration, axis="Focus")

    def stopFocusJog(self):
        self.stopJog(axis="Focus")

    def getFocusLimits(self):
        a = self.convertAxis("Focus")
        sl = self.getSoftwareLimits(axis=a)
        if self.limits[a][0] is not None:
            ll = sl[0]
        else:
            ll = -self.max_travel_mm[a]/2
        if self.limits[a][1] is not None:  
            ul = sl[1]
        else:
            ul = self.max_travel_mm[a]/2
        return (ll,ul)
    
    def setFocusLimits(self, limits=None):
        a = self.convertAxis("Focus")
        if limits is None:
            limits = self.limits[a]
        if limits[0] is not None:
            self.setLowerLimit(limits[0], axis=a)
        if limits[1] is not None:
            self.setUpperLimit(limits[1], axis=a)

    def getBPPosition(self, notify=True):
        return self.getPosition(in_mm=True, axis="Build Platform")

    def absMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.absMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Build Platform")

    def relMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.relMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Build Platform")

    def startBPJog(self, speed=None, acceleration=None):
        self.startJog(speed=speed, acceleration=acceleration, axis="Build Platform")

    def stopBPJog(self):
        self.stopJog(axis="Build Platform")

    def getBPLimits(self):
        a = self.convertAxis("Build Platform")
        sl = self.getSoftwareLimits(axis=a)
        if self.limits[a][0] is not None:
            ll = sl[0]
        else:
            ll = -self.max_travel_mm[a]/2
        if self.limits[a][1] is not None:  
            ul = sl[1]
        else:
            ul = self.max_travel_mm[a]/2
        return (ll,ul)
    
    def setBPLimits(self, limits=None):
        a = self.convertAxis("Build Platform")
        if limits is None:
            limits = self.limits[a]
        elif limits == "calibration":
            limits = self.calibration_limits[a]
        if limits[0] is not None:
            self.setLowerLimit(limits[0], axis=a)
        if limits[1] is not None:
            self.setUpperLimit(limits[1], axis=a)

    ################################# End parent class functions #######################################

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
            self.log.info("Move axis %s to relative position %.4f", a, self.cntsToMm(cnts, axis=a))
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
            self.log.info("Move axis %s to absolute position %.4f", a, self.cntsToMm(cnts, axis=a))
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
                self.logging_move_status[a] = 3
                break

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

    def setup_log_file(self, filename):
        """Set the log file."""
        if self.movement_log is None and filename is not None:
            self.movement_log = str(Path(filename) / "galil_movement_data.csv")
            async_file_hander.write(self.movement_log, "timestamp,")
            for a in self.axes_common_names:
                async_file_hander.write(self.movement_log, f"{a} position_mm,")
                async_file_hander.write(self.movement_log, f"{a} status,")
            async_file_hander.write(self.movement_log, "\n")
        elif self.movement_log is not None and filename is None:
            self.movement_log = None

    def logging_start(self):
        """
        Starts collecting position data
        """
        if not self.logging_running:
            self.movement_log_times = []
            self.movement_log_array = []
            self.logging_running = True
            self.log.info("Galil logging started")

    def logging_stop(self):
        """
        Stops collecting position data
        """

        if self.logging_running:
            self.logging_running = False
            self.log.info("Galil logging stopped")

    def get_logging_results(self):
        return self.movement_log_times, self.movement_log_array

    def loop(self):
        try:
            while self.thread_running:
                # for a in self.axes:
                #     self.current_position[a] = self.getPosition(in_mm=False, notify=False, axis=a)
                pos_dict = self.getPosition(in_mm=False, axis=self.axes, notify=False)
                for a in self.axes:
                    self.current_position[a] = pos_dict[a]
                if self.logging_running:
                    if self.movement_log is not None:
                        tmp = ""
                        for a in self.axes:
                            position = self.current_position[a]
                            tmp += f"{self.cntsToMm(position, axis=a)},"
                            tmp += f"{self.logging_move_status[a]},"
                        self.write_to_disk(tmp)
                    else:
                        # tmp = []
                        # for a in self.axes:
                        #     position = self.current_position[a]
                        #     tmp.append(self.cntsToMm(position, axis=a))
                        tmp = self.cntsToMm(self.current_position[self.default_axis])

                        self.movement_log_times.append(time.time())
                        self.movement_log_array.append(tmp)

                    for a in self.axes:
                        if self.logging_move_status[a] >= 2:
                            self.logging_move_status[a] = -1

                time.sleep(0.01)
        except Exception as ex:
            self.current_position = None
            self.log.warning("Galil loop failed (%s)", ex, exc_info=True)
            self.thread_running = False

    def downloadProgram(self, filename):
        """Download a DMC file to the Galil controller."""
        self.log.info("Downloading '%s' to controller...", filename)
        return self.g.GProgramDownloadFile(filename)

    def interactiveMode(self):
        """Start interactive mode.

        This will leave you on a python prompt that forwards commands to
        the controller. Exits with KeyboardInterrupt.
        """
        if self.connected is None or not self.connected:
            msg = "Must be connected to Galil controller to run interactive mode"
            self.log.critical(msg)
            sys.exit(msg)
        try:
            while True:
                cmd = input("Give Galil a command>> ")
                cmd.strip()
                print(f"{self.send(cmd.upper())}")
        except KeyboardInterrupt:
            print(f"\nExited by KeyboardInterrupt")


if __name__ == "__main__":
    g = Galil(log_level=logging.DEBUG)
    g.connect(exit)
    g.interactiveMode()
