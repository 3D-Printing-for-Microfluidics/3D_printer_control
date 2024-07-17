"""ACS control module."""
import sys
import time
import atexit
import socket
import logging
import threading
from pathlib import Path
from datetime import datetime
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander

from printer_server.drivers.generic_drivers import BPStageDriver, XYStageDriver

class ACS(BPStageDriver, XYStageDriver):
    def __init__(
        self,
        config_dict=None,
        log_level=logging.DEBUG,
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.movement_log = None
        self.config_dict = config_dict

        self.sendLock = threading.Lock()

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

        self.connected = None
        self.initialized = None

        self.socket = None

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
        return self.getPosition()

    def goToBPmax(self):
        self.absMove(mm=self.top_position, axis="Build Platform")
        return self.getPosition()

    def goToBPmin(self):
        self.absMove(mm=self.bottom_position, axis="Build Platform")
        return self.getPosition()

    def connect(self, shutdown):
        """Find the first ACS controller and connect to it."""
        if self.connected is None:
            attempts=10
            timeout=1
            
            self.connected = False
            self.address = self.config_dict["address"]
            self.port = self.config_dict["port"]
            self.log.info("Connecting to ACS (%s), this may take up to 1 minute...", self.address)
            i = 0
            while i < attempts:  # try up to attempts number of times to create a connection
                i += 1
                try:
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.socket.settimeout(10)
                    self.socket.connect((self.address, self.port))
                    self.connected = True
                    self.shutdown = shutdown
                    
                except (OSError, socket.timeout) as e:
                    self.log.info("%s. Retrying in %s second(s)", e, timeout)
                    self.socket = None  # get rid of handle to bad socket
                    time.sleep(timeout)  # wait to try again
            if not self.connected:
                msg = f"ACS controller not found!"
                self.log.critical(msg)
                return False
            
            # self.thread_running = True
            # self.thread.start()
            atexit.register(self.disconnect)
            self.log.info("Connected to ACS controller")
            return True
        else:
            while self.connected is False:
                time.sleep(0.1)

    def disconnect(self):
        """Disconnect form the ACS controller."""
        if self.connected is not None and self.connected is not False:
            self.thread_running = False
            try:
                self.thread.join()
            except RuntimeError:
                pass
            self.thread = Thread(self.log, name="acs_loop_thread", target=self.loop)
            self.thread.daemon = True

            self.connected = None
            self.initialized = None
            try:
                if self.socket is not None:
                    with self.sendLock:
                        self.socket.close()
                    self.socket = None
                self.log.info("Disconnected from ACS controller")
            except:
                self.log.error("Unexpected error on disconnect")

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
        with self.sendLock:
            if notify:
                self.log.debug("Sent : '%s'", command)
            response = self._send(command)
            response = "".join(response)
            self.log.debug("Reply: '%s'", response)
            if response != "":
                if notify:
                    self.log.debug("Reply: '%s'", response)
                if response[0] == '?':
                    self.log.error("Last command '%s' returned error '%s (%s)'", command, response, self.send(f"?{response}"))
            return response
                
    def _send(self, msg):
        msg += "\r"
        encoded_message = msg.encode()
        try:
            self.socket.sendall(encoded_message)
        except socket.timeout:
            msg = "ACS controller send timed out!"
            self.log.critical(msg)
            self.shutdown(is_critical = True)
            sys.exit(msg)
        except Exception as ex:
            self.log.error("Failed to send packet: %s", ex)

        try:
            msg = self.socket.recv(1024).decode()
            return msg.strip()[:-1].strip()
        except socket.timeout:
            msg = "ACS controller recieve timed out!"
            self.log.critical(msg)
            self.shutdown(is_critical = True)
            sys.exit(msg)
        except Exception as e:
            self.log.error("Failed to receive packet: %s", e)
        return None

    def checkLimits(self, axis=None):
        """Return a tuple the state of the limit switches for the
        specified axis.
        """
        a = self.convertAxis(axis)
        # with self.sendLock:
        #     lf = sp.GetSafetyInput(self.acs, a, sp.SafetyControlMasks.ACSC_SAFETY_RL, sp.SYNCHRONOUS, True) #FAULT(axis).#RL pg 250
        #     lr = sp.GetSafetyInput(self.acs, a, sp.SafetyControlMasks.ACSC_SAFETY_LL, sp.SYNCHRONOUS, True) #FAULT(axis).#LL pg 250
        lr = float(self.send(f"?FAULT{a}.#SRL")) # SRL is software limit RL is hardware
        ll = float(self.send(f"?FAULT{a}.#SLL")) # SLL is software limit LL is hardware
        return bool(lr), bool(ll)

    def getPosition(self, axis=None, notify=True):
        """Return the position of the specified encoder."""
        a = self.convertAxis(axis)
        # with self.sendLock:
        #     pos = sp.GetFPosition(self.acs, a, sp.SYNCHRONOUS, True)
        pos = self.send(f"?FPOS{a}", notify=notify)
        return float(pos)

    def motorOn(self, axis=None):
        """Turn on the specified axis."""
        a = self.convertAxis(axis)
        # with self.sendLock:
        #     sp.Enable(self.acs, a, sp.SYNCHRONOUS, True) # ENABLE pg 96
        self.send(f"ENABLE {a}")

    def motorOff(self, axis=None):
        """Turn off the specified axis."""
        a = self.convertAxis(axis)
        self.log.warning("Axis %s motor turned off. It may sink due to gravity.", a)
        # with self.sendLock:
        #     sp.Disable(self.acs, a, sp.SYNCHRONOUS, True) # DISABLE pg 96
        self.send(f"DISABLE {a}")

    def getAcceleration(self, axis=None):
        """Return the acceleration of the specified axis (mm/sec^2)."""
        a = self.convertAxis(axis)
        # with self.sendLock:
        #     acc = sp.GetAcceleration(self.acs, a, sp.SYNCHRONOUS, True) # ACC 2pg 372
        acc = self.send(f"?ACC{a}")
        return float(acc)

    def setAcceleration(self, acceleration, axis=None):
        """Set the acceleration for the specified axis (mm/sec^2)."""
        a = self.convertAxis(axis)
        # with self.sendLock:
        #     sp.SetAcceleration(self.acs, a, acceleration, sp.SYNCHRONOUS, True) 
        #     sp.SetDeceleration(self.acs, a, acceleration, sp.SYNCHRONOUS, True)

        self.send(f"ACC({a}) = {acceleration}")
        self.send(f"DEC({a}) = {acceleration}")

    def getSpeed(self, axis=None):
        """Return the speed for the specified axis (mm/sec)."""
        a = self.convertAxis(axis)
        # with self.sendLock:
        #     speed = sp.GetVelocity(self.acs, a, sp.SYNCHRONOUS, True)
        speed = self.send(f"?VEL{a}")
        return float(speed)

    def setSpeed(self, speed, axis=None):
        """Set the speed for the specified axis (mm/sec)."""
        a = self.convertAxis(axis)
        # with self.sendLock:
        #     sp.SetVelocity(self.acs, a, speed, sp.SYNCHRONOUS, True)
        self.send(f"VEL({a}) = {speed}")

    def wait_for_buffer_completion(self, buffer_number, check_interval=1):
        while True:
            response = self.send(f"?{8}")
            if "terminated" in response:
                self.log.debug("Buffer execution completed")
                break
            self.log.debug("Buffer still running...")
            time.sleep(check_interval)

    def home(self):
        """Run the homing routine."""
        self.log.info("Start homing...")

        # self.RunBuffer(self.acs, 8, "homeA", sp.SYNCHRONOUS, True) # START pg 92
        self.send(f"START 8, homeX")
        self.wait_for_buffer_completion(8)
        self.send(f"START 8, homeY")
        self.wait_for_buffer_completion(8)
        # self.send(f"START 8, homeA")
        # self.wait_for_buffer_completion(8)

        for a in self.axes:
            # self.waitForMotionComplete(0, axis=a)
            self.homed[a] = True  # update class homed status
        self.log.info("Homing complete.")

        for a in self.axes:
            self.setSpeed(self.getDefaultSpeed(a), axis=a)
            self.setAcceleration(self.getDefaultAcceleration(a), axis=a)

    ################################# Parent class functions #######################################

    def getXYPosition(self, axis=None, notify=True):
        return self.getPosition(axis=axis, notify=notify)

    def absMoveXY( self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        self.absMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)

    def relMoveXY(self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        self.relMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)

    def startXYJog(self, speed=None, acceleration=None, axis=None):
        self.startJog(speed=speed, acceleration=acceleration, axis=axis)

    def stopXYJog(self, axis=None):
        self.stopJog(axis=axis)

    def getBPPosition(self, notify=True):
        return self.getPosition(axis="Build Platform", notify=notify)

    def absMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.absMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Build Platform")

    def relMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.relMove(mm=mm, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis="Build Platform")

    def startBPJog(self, speed=None, acceleration=None):
        self.startJog(speed=speed, acceleration=acceleration, axis="Build Platform")

    def stopBPJog(self):
        self.stopJog(axis="Build Platform")

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
            self.log.info("Move axis %s to relative position %s", a, mm)
            # with self.sendLock:
            #     sp.ToPoint(self.acs, sp.MotionFlags.ACSC_AMF_, a, mm, sp.SYNCHRONOUS, True) # PTP pg 108
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
            self.log.info("Move axis %s to absolute position %s", a, mm)
            # with self.sendLock:
            #     sp.ToPoint(self.acs, None, a, mm, sp.SYNCHRONOUS, True) # PTP pg 108
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
        # with self.sendLock:
        #     sp.Jog(self.acs, sp.MotionFlags.ACSC_AMF_VELOCITY, a, speed, sp.SYNCHRONOUS, True) # JOG pg 127
        if speed > 0:
            self.send(f"JOG/v {a}, {speed}, +")
        else:
            self.send(f"JOG/v {a}, {speed}, -")
        self.logging_move_status[a] = 0

    def stopJog(self, axis=None):
        """Stop a jog, non-blocking."""
        a = self.convertAxis(axis)
        self.log.info("Stop jog on axis %s", a)
        # with self.sendLock:
        #     sp.Kill(self.acs, a, sp.SYNCHRONOUS, True) # sp.Halt uses full decelleration. I think a quick stop may be better... KILL pg 99
        self.send(f"KILL/e {a}")
        self.logging_move_status[a] = -1
        self.jogging[a] = False
        self.setSpeed(self.pre_jog_speed[a])
        self.setAcceleration(self.pre_jog_acceleration[a])

    # WaitMotionEnd # Waits for Motion Compete and settling
    # GetMotorState # Bit order (0: enabled, 1:loop control, 4:settled, 5:moving, 6:accelerating, 25:settledA, 26:settledB, 27:settledC)

    def waitForMotionComplete(self, mm, wait_for_settling=True, axis=None):
        """Blocks execution until the encoder reaches the target value
        and saves motion data as it goes.
        """
        a = self.convertAxis(axis)
        # self.WaitMotionEnd(self.acs, a, -1, True)
        counter = 0
        time_count = 0
        limit_switch_triggered = False
        in_motion = float(self.send(f"?MST{a}.#INPOS", notify=False))
        while in_motion == 1.0:
            time.sleep(0.01)
            in_motion = float(self.send(f"?MST{a}.#INPOS", notify=False))
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
                if int(mm - error) <= position <= int(mm + error):
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

    def loop(self):
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
                    # tmp = []
                    # for a in self.axes:
                    #     position = self.current_position[a]
                    #     tmp.append(position, axis=a)
                    tmp = self.current_position[self.default_axis]

                    self.movement_log_times.append(time.time())
                    self.movement_log_array.append(tmp)

                for a in self.axes:
                    if self.logging_move_status[a] >= 2:
                        self.logging_move_status[a] = -1

                time.sleep(0.01)

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
            while True:
                cmd = input("Give ACS a command>> ")
                cmd.strip()
                with self.sendLock:
                    print(self.send(cmd))
        except KeyboardInterrupt:
            print("\nExited by KeyboardInterrupt")
        except:
            print("\nError processing command")


if __name__ == "__main__":
    g = ACS(log_level=logging.DEBUG)
    g.connect()
    g.interactiveMode()
