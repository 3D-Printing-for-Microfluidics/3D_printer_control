"""ACS control module."""
import sys
import time
import atexit
import socket
import logging
from pathlib import Path
from datetime import datetime
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander

from printer_server.drivers.generic_drivers import EthernetSerial, BPStageDriver, XYStageDriver

class ACS(EthernetSerial, BPStageDriver, XYStageDriver):
    def __init__(
        self,
        config_dict=None,
        log_level=logging.DEBUG,
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__("ACS", host=config_dict["address"], port=config_dict["port"], logger=self.log)

        self.movement_log = None
        self.config_dict = config_dict

        self.thread = Thread(self.log, name="acs_loop_thread", target=self.loop)
        self.thread.daemon = True
        self.thread_running = False
        self.logging_running = False

        self.default_axis = config_dict["default_axis"]
        self.axes = config_dict["axes"]
        self.axes_common_names = config_dict["axes_common_names"]
        self.max_travel_mm = config_dict["axes_travel"]
        self.default_speed = config_dict["axes_speed"]
        self.default_acceleration = config_dict["axes_acceleration"]
        self.mirroring = config_dict["mirroring"]
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
            self.error_window[a] = self.tolerence[a] / 1000
            self.monitoring_window[a] = self.error_window[a] * 100
            self.logging_move_status[a] = -1
            self.current_position[a] = 0

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
        self.log.info("Initializing ACS...")
        # Homing routine already takes care of this...
        # for axis in self.axes:
        #     self.motorOn(axis)
        self.log.info("Initialized ACS")

    def connect(self):
        """Find the first ACS controller and connect to it."""
        ret = super().connect()
        if ret is not None and ret and not self.thread_running:
            self.thread_running = True
            self.thread.start()
        return ret

    def disconnect(self):
        """Disconnect form the ACS controller."""
        if self.connected is not None and self.connected is not False and self.socket is not None:
            self.thread_running = False
            try:
                self.thread.join()
                self.thread = Thread(self.log, name="acs_loop_thread", target=self.loop)
                self.thread.daemon = True

                for axis in self.axes:
                    self.motorOff(axis)
            except:
                pass
            
            super().disconnect()

    def write_to_disk(self, *args):
        """Write data to disk using the async file handler class.

        Log location must be set for data to be saved.
        """
        ts = "%Y-%m-%d %H:%M:%S.%f"
        async_file_hander.write(self.movement_log, datetime.now().strftime(ts) + ",")
        async_file_hander.write(self.movement_log, ",".join(map(str, args)) + "\n")

    def send(self, command, notify=True):
        """Send a command to the controller.

        If an error is returned, request and also return more
        information about the error.
        """
        response = super().send(command, notify=notify)
        response = response.strip()[:-1].strip()
        if response != "":
            if response[0] == '?':
                self.log.error("Last command '%s' returned error '%s (%s)'", command, response, self.send(f"?{response}"))
        return response
    
    def getSoftwareLimits(self, axis=None):
        a = self.convertAxis(axis)
        ll = self.send(f"?SLLIMIT({a})")
        ul = self.send(f"?SRLIMIT({a})")
        if self.mirroring[a]:
            return (-float(ul), -float(ll))
        return (float(ll), float(ul))
    
    def setLowerLimit(self, limit, axis=None):
        a = self.convertAxis(axis)
        if limit is None:
            limit = -self.max_travel_mm[a]
        if self.mirroring[a]:
            self.send(f"SRLIMIT({a}) = {-limit}")
        else:
            self.send(f"SLLIMIT({a}) = {limit}")

    def setUpperLimit(self, limit, axis=None):
        a = self.convertAxis(axis)
        if limit is None:
            limit = self.max_travel_mm[a]
        if self.mirroring[a]:
            self.send(f"SLLIMIT({a}) = {-limit}")
        else:
            self.send(f"SRLIMIT({a}) = {limit}")
            
    def checkLimits(self, axis=None):
        """Return a tuple the state of the limit switches for the
        specified axis.
        """
        a = self.convertAxis(axis)
        lr = float(self.send(f"?FAULT{a}.#SRL")) # SRL is software limit RL is hardware
        ll = float(self.send(f"?FAULT{a}.#SLL")) # SLL is software limit LL is hardware
        if self.mirroring[a]:
            return bool(ll), bool(lr)
        return bool(lr), bool(ll)

    def getPosition(self, axis=None, notify=True):
        """Return the position of the specified encoder."""
        a = self.convertAxis(axis)
        pos = self.send(f"?FPOS{a}", notify=notify)
        pos = round(float(pos), 4)
        if self.mirroring[a]:
            return -float(pos)
        return float(pos)

    def motorOn(self, axis=None):
        """Turn on the specified axis."""
        self.log.debug("Turning ACS %s motor on", axis)
        a = self.convertAxis(axis)
        self.send(f"ENABLE {a}")

    def motorOff(self, axis=None):
        """Turn off the specified axis."""
        a = self.convertAxis(axis)
        self.log.warning("Axis %s motor turned off. It may sink due to gravity.", a)
        self.send(f"DISABLE {a}")

    def getAcceleration(self, axis=None):
        """Return the acceleration of the specified axis (mm/sec^2)."""
        a = self.convertAxis(axis)
        acc = self.send(f"?ACC{a}")
        return float(acc)

    def setAcceleration(self, acceleration, axis=None):
        """Set the acceleration for the specified axis (mm/sec^2)."""
        a = self.convertAxis(axis)
        self.send(f"ACC({a}) = {acceleration}")
        self.send(f"DEC({a}) = {acceleration}")

    def getSpeed(self, axis=None):
        """Return the speed for the specified axis (mm/sec)."""
        a = self.convertAxis(axis)
        speed = self.send(f"?VEL{a}")
        return float(speed)

    def setSpeed(self, speed, axis=None):
        """Set the speed for the specified axis (mm/sec)."""
        a = self.convertAxis(axis)
        self.send(f"VEL({a}) = {speed}")

    def wait_for_buffer_completion(self, buffer_number, check_interval=0.1):
        while True:
            response = self.send(f"?{buffer_number}")
            if "terminated" in response:
                self.log.debug("Buffer execution completed")
                break
            self.log.debug("Buffer still running...")
            time.sleep(check_interval)

    def home(self):
        """Run the homing routine."""
        self.log.info("Start homing...")

        self.send(f"START 0, 1")
        self.wait_for_buffer_completion(0)

        for a in self.axes:
            self.homed[a] = True  # update class homed status
        self.log.info("Homing complete.")

        for a in self.axes:
            self.setSpeed(self.getDefaultSpeed(a), axis=a)
            self.setAcceleration(self.getDefaultAcceleration(a), axis=a)

    ################################# Parent class functions #######################################
            
    def goToBPcalibration(self):
        self.absMove(mm=self.calibration_position, axis="Build Platform")
        return self.getPosition()

    def goToBPtop(self):
        self.absMove(mm=self.top_position, axis="Build Platform")
        return self.getPosition()

    def goToBPbottom(self):
        self.absMove(mm=self.bottom_position, axis="Build Platform")
        return self.getPosition()

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
        return self.getPosition(axis=axis, notify=notify)

    def absMoveXY(self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        mm = round(mm, 4)
        self.absMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)
        if axis == "X":
            self.prev_x_position = mm
        elif axis == "Y":
            self.prev_y_position = mm

    def relMoveXY(self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        mm = round(mm, 4)
        self.relMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)
        if axis == "X":
            if self.prev_x_position is not None:
                self.prev_x_position += mm
        elif axis == "Y":
            if self.prev_y_position is not None:
                self.prev_y_position += mm

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
        self.setLowerLimit(limits[0], axis=a)
        self.setUpperLimit(limits[1], axis=a)

    def getBPPosition(self, notify=True):
        return self.getPosition(axis="Build Platform", notify=notify)

    def absMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        mm = round(mm, 4)
        self.absMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Build Platform")
        self.prev_bp_position = mm

    def relMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        mm = round(mm, 4)
        self.relMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Build Platform")
        if self.prev_bp_position is not None:
            self.prev_bp_position += mm

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
        self.setLowerLimit(limits[0], axis=a)
        self.setUpperLimit(limits[1], axis=a)

    ################################# End parent class functions #######################################

    # pylint: disable=too-many-arguments
    def relMove(self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
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
            start_position = self.getPosition(axis=a)
            self.log.info("Move axis %s to relative position %.4f", a, mm)
            if self.mirroring[a]:
                self.send(f"PTP/r {a}, {-mm}")
            else:
                self.send(f"PTP/r {a}, {mm}")
            self.logging_move_status[a] = 0
            self.waitForMotionComplete(start_position + mm, wait_for_settling=wait_for_settling, axis=a)
        if speed is not None:
            self.setSpeed(old_speed, axis=a)
        if acceleration is not None:
            self.setAcceleration(old_acceleration, axis=a)
        return self.getPosition(axis=a)

    # pylint: disable=too-many-arguments
    def absMove(
        self,
        mm=None,
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
            return self.getPosition(axis=a)
        old_speed = None
        old_acceleration = None
        if speed is not None:
            old_speed = self.getSpeed(axis=a)
            self.setSpeed(speed, axis=a)
        if acceleration is not None:
            old_acceleration = self.getAcceleration(axis=a)
            self.setAcceleration(acceleration, axis=a)
        if mm is not None:
            self.log.info("Move axis %s to absolute position %.4f", a, mm)
            if self.mirroring[a]:
                self.send(f"PTP {a}, {-mm}")
            else:
                self.send(f"PTP {a}, {mm}")
            self.logging_move_status[a] = 0
            self.waitForMotionComplete(mm, wait_for_settling=wait_for_settling, axis=a)
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
            )  # save the acceleration before jogging begins
        self.jogging[a] = True

        self.setAcceleration(acceleration)
        self.log.info("Start jog on axis %s at speed %s mm/sec", a, speed)
        if self.mirroring[a]:
            speed = -speed
        self.send(f"JOG/v {a}, {speed}, +")
        self.logging_move_status[a] = 0

    def stopJog(self, axis=None):
        """Stop a jog, non-blocking."""
        a = self.convertAxis(axis)
        self.log.info("Stop jog on axis %s", a)
        self.send(f"KILL/e {a}")
        self.logging_move_status[a] = -1
        self.jogging[a] = False
        self.setSpeed(self.pre_jog_speed[a])
        self.setAcceleration(self.pre_jog_acceleration[a])

    def waitForMotionComplete(self, mm, wait_for_settling=True, axis=None):
        """Blocks execution until the encoder reaches the target value
        and saves motion data as it goes.
        """
        a = self.convertAxis(axis)
        counter = 0
        time_count = 0
        limit_switch_triggered = False
        time.sleep(0.01)
        in_motion = bool(int(self.send(f"?MST{a}.#MOVE", notify=False)))
        in_position = bool(int(self.send(f'?MST{a}.#INPOS', notify=False)))
        while in_motion or not in_position:
            time.sleep(0.01)
            in_motion = bool(int(self.send(f"?MST{a}.#MOVE", notify=False)))
            in_position = bool(int(self.send(f'?MST{a}.#INPOS', notify=False)))
            upper, lower = self.checkLimits(axis=a)
            position = self.current_position[a]
            if (
                not limit_switch_triggered
                and (lower and mm < position)
                or (upper and mm > position)
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
                if float(mm - error) <= position <= float(mm + error):
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
                        mm,
                    )
                    break
        # self.logging_move_complete = True
        self.logging_move_status[a] = 2

    def setup_log_file(self, filename):
        """Set the log file."""
        if self.movement_log is None and filename is not None:
            self.movement_log = str(Path(filename) / "acs_movement_data.csv")
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
            self.log.info("ACS logging started")

    def logging_stop(self):
        """
        Stops collecting position data
        """
        if self.logging_running:
            self.logging_running = False
            self.log.info("ACS logging stopped")

    def get_logging_results(self):
        return self.movement_log_times, self.movement_log_array

    def loop(self):
        try:
            while self.thread_running:
                for a in self.axes:
                    self.current_position[a] = self.getPosition(notify=False, axis=a)
                if self.logging_running:
                    if self.movement_log is not None:
                        tmp = ""
                        for a in self.axes:
                            position = self.current_position[a]
                            tmp += f"{position},"
                            tmp += f"{self.logging_move_status[a]},"
                        self.write_to_disk(tmp)
                    else:
                        tmp = self.current_position[self.default_axis]

                        self.movement_log_times.append(time.time())
                        self.movement_log_array.append(tmp)

                    for a in self.axes:
                        if self.logging_move_status[a] >= 2:
                            self.logging_move_status[a] = -1

                time.sleep(0.01)
        except Exception as ex:
            self.current_position = None
            self.log.warning("ACS loop failed (%s)", ex, exc_info=True)
            self.thread_running = False

    def interactiveMode(self):
        """Start interactive mode.

        This will leave you on a python prompt that forwards commands to
        the controller. Exits with KeyboardInterrupt.
        """
        if self.connected is None or not self.connected:
            msg = "Must be connected to ACS controller to run interactive mode"
            self.log.critical(msg)
            sys.exit(msg)
        try:
            import threading
            sendLock = threading.Lock()
            while True:
                cmd = input("Give ACS a command>> ")
                cmd.strip()
                with sendLock:
                    print(f"{self.send(cmd)}")
        except KeyboardInterrupt:
            print(f"\nExited by KeyboardInterrupt")
        except:
            print(f"\nError processing command")


if __name__ == "__main__":
    g = ACS(log_level=logging.DEBUG)
    g.connect()
    g.interactiveMode()
