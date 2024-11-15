import os
import time
import math
import atexit
import logging
import threading
import traceback
from pathlib import Path
from datetime import datetime

from pipython import GCSDevice, pitools
from pipython.pidevice.gcscommands import GCSCommands
from pipython.pidevice.gcsmessages import GCSMessages
from printer_server.threading_wrapper import Thread
from printer_server.drivers.hexapod.pisocket import PISocket
from printer_server.async_file_handler import async_file_hander

from printer_server.drivers.generic_drivers import TTRStageDriver, FocusStageDriver
from printer_server.views.calibration import (
    get_last_calibration_positions_from_logs,
)

def radians_to_degrees(radians):
    return radians * (180 / math.pi)

def degrees_to_radians(degrees):
    return degrees * (math.pi / 180)

class Hexapod(TTRStageDriver, FocusStageDriver):
    def __init__(self, config_dict=None, log_level=logging.INFO):
        """ HexapodController

        Args:
            log_directory (str): root directory where the log file of this controller will be stored
        """
        super().__init__()
        
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.thread = Thread(self.log, name="hexapod_loop_thread", target=self.loop)
        self.thread.daemon = True
        self.thread_running = False
        self.logging_running = False

        self.config_dict = config_dict
        self.movement_log = None
        self.connected = None
        self.axes = config_dict["axes"]
        self.axes_common_names = config_dict["axes_common_names"]
        self.limits = config_dict["limits"]
        self.gateway = PISocket("Hexapod", host=self.config_dict["address"], port=self.config_dict["port"], logger=self.log)

    def connect(self):
        """ Run routine for connecting to the hexapod and reference it if it hasn't been referenced yet upon powerup
        """
        if self.connected is None:
            self.connected = False
            if not self.gateway.connect():
                self.connected = None
                return False
            messages = GCSMessages(self.gateway)
            self.controller = GCSCommands(gcsmessage=messages)
            self.connected = True 
            atexit.register(self.disconnect)
            self.log.info("Connected to hexapod")
            return True
        else:
            while self.connected is False:
                time.sleep(0.1)
        return None
    
    def initialize(self):
        # check if it has been referenced, else do referencing
        self.log.info("Initializing hexapod...")
        with self.gateway.sendLock:
            referenced_axes_flags = self.controller.qFRF() # ourput: referenced_axes_flags: OrderedDict([('X', True), ('Y', True), ('Z', True), ('U', True), ('V', True), ('W', True)])
        if False in referenced_axes_flags.values():
            self.reference_axes()
        self.log.info("Initialized hexapod")

        self.thread_running = True
        self.thread.start()

    def disconnect(self):
        """ Close connection to the hexapod
        """
        if self.connected is not None and self.connected:
            self.thread_running = False
            self.thread.join()
            self.thread = Thread(self.log, name="hexapod_loop_thread", target=self.loop)
            self.thread.daemon = True

            self.connected = None
            # self.controller.CloseConnection()
            self.gateway.disconnect()
            self.log.info("Disconnected from hexapod")

    def convertAxis(self, axis):
        """Return converted axis name (eg. maps X,Y,Z to A,B,C)"""
        for i in range(len(self.axes)):
            if axis in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
            if axis.upper() in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
        raise ValueError("Invalid axis supplied")


    ################################# Parent class functions #######################################
    def home(self):
        self.home_all_axes()
        calibration_positions = get_last_calibration_positions_from_logs()
        x = calibration_positions.get("pivot_x",0)/1000
        y = calibration_positions.get("pivot_y",0)/1000
        z = calibration_positions.get("pivot_z",0)/1000
        self.set_pivot_point(x,y,z)

        # pipython.pidevice.gcserror.GCSError

    def getTTRPosition(self, axis=None, notify=True):
        return self.get_pose(self.convertAxis(axis))

    def absMoveTTR(self, rad=None, axis=None):
        self.move_to_angle_axis(axis, rad)

    def relMoveTTR(self, rad=None, axis=None):
        self.step_axis(self.convertAxis(axis), rad)

    def getTTRLimits(self, axis=None):
        a = self.convertAxis(axis)
        sdr = self.get_simple_dynamic_range(a)
        sl = self.getSoftwareLimits(axis=a)
        if self.limits[a][0] is not None:
            ll = max(sdr[0], sl[0])
        else:
            ll = sdr[0]
        if self.limits[a][1] is not None:  
            ul = min(sdr[1], sl[1])
        else:
            ul = sdr[1]
        return (ll,ul)
    
    def setTTRLimits(self, limits=None, axis=None):
        a = self.convertAxis(axis)
        if limits is None:
            limits = self.limits[a]
        if limits[0] is not None:
            self.setLowerLimit(limits[0], axis=a)
        if limits[1] is not None:
            self.setUpperLimit(limits[1], axis=a)

    def write_to_disk(self, *args):
        """Write data to disk using the async file handler class.

        Log location must be set for data to be saved.
        """
        ts = "%Y-%m-%d %H:%M:%S.%f"
        async_file_hander.write(self.movement_log, datetime.now().strftime(ts) + ",")
        async_file_hander.write(self.movement_log, ",".join(map(str, args)) + "\n")

    def setup_log_file(self, filename):
        """Set the log file."""
        if self.movement_log is None and filename is not None:
            self.movement_log = str(Path(filename) / "hexapod_movement_data.csv")
            async_file_hander.write(self.movement_log, "timestamp,")
            for a in self.axes_common_names:
                async_file_hander.write(self.movement_log, f"{a} position,")
            async_file_hander.write(self.movement_log, "\n")
        elif self.movement_log is not None and filename is None:
            self.movement_log = None

    def logging_start(self):
        """
        Starts collecting position data
        """
        if not self.logging_running:
            self.logging_running = True
            self.log.info("Hexapod logging started")

    def logging_stop(self):
        """
        Stops collecting position data
        """
        if self.logging_running:
            self.logging_running = False
            self.log.info("Hexapod logging stopped")

    def loop(self):
        try:
            while self.thread_running:
                pose = self.get_pose()
                if self.logging_running:
                    if self.movement_log is not None:
                        tmp = ""
                        for a in self.axes:
                            tmp += f"{pose[a]},"
                        self.write_to_disk(tmp)
                    time.sleep(0.1)
        except Exception as ex:
            self.log.warning("Hexapod loop failed (%s)", ex, exc_info=True)
            self.thread_running = False

    def getDefaultFocusSpeed(self):
        return 0

    def getDefaultFocusAcceleration(self):
        return 0

    def getFocusPosition(self, notify=True):
        return self.get_pose("Focus")

    def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.move_to_position_axis("Focus", mm)

    def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.step_axis("Focus", mm)

    def startFocusJog(self, speed=None, acceleration=None):
        self.log.error("Hexapod Jogging not implemented")

    def stopFocusJog(self):
        self.log.error("Hexapod Jogging not implemented")

    def getFocusLimits(self):
        a = self.convertAxis("Focus")
        sdr = self.get_simple_dynamic_range(a)
        sl = self.getSoftwareLimits(axis=a)
        if self.limits[a][0] is not None:
            ll = max(sdr[0], sl[0])
        else:
            ll = sdr[0]
        if self.limits[a][1] is not None:  
            ul = min(sdr[1], sl[1])
        else:
            ul = sdr[1]
        return (ll,ul)
    
    def setFocusLimits(self, limits=None):
        a = self.convertAxis("Focus")
        if limits is None:
            limits = self.limits[a]
        if limits[0] is not None:
            self.setLowerLimit(limits[0], axis=a)
        if limits[1] is not None:
            self.setUpperLimit(limits[1], axis=a)

    ################################# End parent class functions #######################################
        
    def get_status(self):
        """ Retrieve any error codes from the hexapod

        Returns:
            int: error code
        """
        with self.gateway.sendLock:
            status = self.controller.qERR()
        self.log.info("Querying hexapod error code number: %s", status)
        return status

    def reference_axes(self):
        """ Run routine for referencing all the axes of the hexapod
        """
        self.log.info("Referencing axes...")
        with self.gateway.sendLock:
            self.controller.FRF()
        self.gateway.waitontarget(self.controller)
        self.log.info("Referencing axes completed")
    
    def home_all_axes(self):
        """ Home all the axes in the hexapod
        """
        self.log.info("Homing axes...")
        self.set_pose(0,0,0,0,0,0, suppress_message=True)
        self.log.info("Homing axes completed")

    def move_to_position_axis(self, axis, value):
        """ Perform absolute displacement of axis to target value

        Args:
            axis (str): which axis is being actuated (e.g. 'X', 'Y', or 'Z')
            value (float): target position in mm for the given axis
        """
        axis = self.convertAxis(axis)
        self.log.info("Translating axis %s to %.3f [mm]", axis, value)
        with self.gateway.sendLock:
            self.controller.MOV(axis, value)
        self.gateway.waitontarget(self.controller)

    def move_to_position_compound(self, x, y, z):
        """ Perform absolute simultaneous translation of all translational axes to the specified positions in X, Y, and Z 

        Args:
            x (float): 'X' axis target position
            y (float): 'Y' axis target position
            z (float): 'Z' axis target position
        """
        params = [x, y, z]
        for param in params:
            if param == None:
                self.log.warning("parameter provided is None. No motion performed")
                return

        self.log.info("Moving to position: (%.3f, %.3f, %.3f) mm", x, y, z)
        with self.gateway.sendLock:
            self.controller.MOV({'X': x, 'Y': y, 'Z': z}, None) # Try this one out!
        self.gateway.waitontarget(self.controller)

    def move_to_angle_axis(self, axis, value):
        """ Perform absolute rotation of axes to the target value

        Args:
            axis (str): which axis is being actuated(e.g. 'U', 'V', or 'W')
            value (float): target position in radians for the given axis
        """
        axis = self.convertAxis(axis)
        deg = radians_to_degrees(value)
        self.log.info("Rotating axis %s to %.4f [rad]", axis, value)
        with self.gateway.sendLock:
            self.controller.MOV(axis, deg)
        self.gateway.waitontarget(self.controller)

    def move_to_angle_compound(self, u, v, w):
        """ Perform absolute simultaneous rotation of all rotational axes to the specified angles in U, V, and W

        Args:
            u (float): 'U' axis target angle
            v (float): 'V' axis target angle
            w (float): 'W' axis target angle
        """
        params = [u, v, w]
        for param in params:
            if type(param) == None:
                self.log.warning("parameter provided is None. No motion performed")
                return
            
        u_deg = radians_to_degrees(u)
        v_deg = radians_to_degrees(v)
        w_deg = radians_to_degrees(w)
        self.log.info("Moving to angle: (%.4f, %.4f, %.4f) [rad]", u, v, w)
        with self.gateway.sendLock:
            self.controller.MOV({'U': u_deg, 'V': v_deg, 'W': w_deg}, None) # Try this one out!
        self.gateway.waitontarget(self.controller)
    
    def set_pose(self, x, y, z, u, v, w, suppress_message=False):
        """ Perform absolute simultaneous translation and rotation of all translational and rotational axes to the specified 
        positions and angles in X, Y, Z, U, V, and W to specify the pose of the coordinate system that corresponds to the current 
        pivot point

        Args:
            x (float): 'X' axis target position
            y (float): 'Y' axis target position
            z (float): 'Z' axis target position
            u (float): 'U' axis target angle
            v (float): 'V' axis target angle
            w (float): 'W' axis target angle
        """
        u_deg = radians_to_degrees(u)
        v_deg = radians_to_degrees(v)
        w_deg = radians_to_degrees(w)
        if not suppress_message:
            self.log.info("Concurrently adjusting the pose to: 'X': %.3f, 'Y': %.3f, 'Z': %.3f, [mm] 'U': %.4f, 'V': %.4f, 'W': %.4f [rad]", x, y, z, u, v, w)
        with self.gateway.sendLock:
            self.controller.MOV({'X': x, 'Y': y, 'Z': z, 'U': u_deg, 'V': v_deg, 'W': w_deg})
        self.gateway.waitontarget(self.controller)


    def step_axis(self, axis, step_size):
        """ Perform relative actuation of the specified axis by the specified step size

        Args:
            axis (str): axis to be actuated (translated or rotated)
            step_size (float): step size of the translation or rotation of the specified axis in microns or milliradians
        """
        axis = self.convertAxis(axis)
        if axis == "U" or axis == "V" or axis == "W":
            deg = radians_to_degrees(step_size) 
            self.log.info("Stepping axis %s by %.4f rad", axis, step_size)
            with self.gateway.sendLock:
                self.controller.MVR(axis, deg)
            self.gateway.waitontarget(self.controller)
        else:
            self.log.info("Stepping axis %s by %.4f mm", axis, step_size)
            with self.gateway.sendLock:
                self.controller.MVR(axis, step_size)
            self.gateway.waitontarget(self.controller)

    def get_pose(self, axis=None):
        """ Get the current pose (translation and rotation) of the coordiante system corresponding to the current pivot point of the system

        Returns:
            list: values of the translational and rotational axes of the hexapod (converted radians)
        """
        if axis is None:
            with self.gateway.sendLock:
                positions_raw = self.controller.qPOS()
            positions_raw["U"] = degrees_to_radians(positions_raw["U"])
            positions_raw["V"] = degrees_to_radians(positions_raw["V"])
            positions_raw["W"] = degrees_to_radians(positions_raw["W"])
            return positions_raw
        else:
            axis = self.convertAxis(axis)
            with self.gateway.sendLock:
                positions_raw = self.controller.qPOS(axis)
            if axis == "U" or axis == "V" or axis == "W":
                position = round(degrees_to_radians(positions_raw[axis]),4)
                self.log.debug("Get %s pos: %.4f", axis, position)
            else:
                position = round(positions_raw[axis], 3)
                self.log.debug("Get %s pos: %.3f", axis, position)
            return position

    def hard_stop(self):
        """ Stop any actuations within the hexapod currently beign executed
        """
        with self.gateway.sendLock:
            self.controller.STP()
        self.log.info("Motion stopped")

    def get_pivot_point(self):
        """ Retrieve the current pivot point

        Returns:
            OrderedDict: dictionary containing the axes and values of the pivot point
        """
        with self.gateway.sendLock:
            return self.controller.qSPI()

    def set_pivot_point(self, r, s, t):
        """ Set the value of the pivot point about which the rotational commands are executed

        Args:
            r (float): 'R' axis target position (corresponding to the equivalent new coordiante system's 'X' axis)
            s (float): 'S' axis target position (corresponding to the equivalent new coordiante system's 'Y' axis)
            t (float): 'T' axis target position (corresponding to the equivalent new coordiante system's 'Z' axis)

        Returns:
            bool: successful change of pivot point
        """
        current_pose = self.get_pose()
        # rotational_axes = current_pose[3:]
        rotational_axes = [
            current_pose["U"],
            current_pose["V"],
            current_pose["W"]
        ]
        all_rotational_axes_zero = True
        for axis in rotational_axes:
            if axis >= 0.000001:
                all_rotational_axes_zero = False
        if all_rotational_axes_zero:
            self.log.info("Setting pivot point to: %.3f, %.3f, %.3f mm", r, s, t)
            with self.gateway.sendLock:
                self.controller.SPI({'R': r, 'S': s, 'T': t})
            self.gateway.waitontarget(self.controller)
            ret_val = self.get_pivot_point()
            return True
        else:
            self.log.warning("Not all rotational axes (U, V, W) are 0. Set them to 0 before attempting pivot point adjustment")
            return False
    
    def step_pivot_point(self, axis, step_size):
        """ Move the pivot point by step_size relative to the current position

        Args:
            axis (str): pivot point axis (e.g. 'R', 'S'. or 'T')
            step_size (float): step size for moving the pivot point in microns
        """
        current_pivot = self.get_pivot_point()
        new_pivot = current_pivot
        if (axis == "R"):
            new_pivot["R"] += step_size

        elif (axis == "S"):
            new_pivot["S"] += step_size

        elif (axis == "T"):
            new_pivot["T"] += step_size

        self.set_pivot_point(new_pivot["R"], new_pivot["S"], new_pivot["T"])
        self.log.info("Pivot point stepped by %.3f mm on %s axis", step_size, axis)
        
    def getSoftwareLimits(self, axis=None):
        a = self.convertAxis(axis)
        with self.gateway.sendLock:
            ll = self.controller.qNLM(a)
            ul = self.controller.qPLM(a)
        return (float(ll[a]), float(ul[a]))

    def setLowerLimit(self, limit, axis=None):
        a = self.convertAxis(axis)
        with self.gateway.sendLock:
            self.controller.NLM({a: limit})

    def setUpperLimit(self, limit, axis=None):
        a = self.convertAxis(axis)
        with self.gateway.sendLock:
            self.controller.PLM({a: limit})

    def get_simple_dynamic_range(self, target_axis:str):
        """ Get the range of motion of the requested axis. Due to the complexity of the hexapod joint configuration, dynamic ranges change if 
        multiple axis are actuated at once (which makes this type of query dependant on target pose), therefore for simplicity this dynamic 
        range query considers only the case where a single axis is actuated, making the computation independent on target pose (see)

        Args:
            target_axis_value (str): desired axis for dynamic range check (e.g. 'U', 'X', 'V', etc.)

        Returns:
            tuple: negative and positive ranges of the requested axis at the given pose
        """
        try:
            target_axis = self.convertAxis(target_axis)
            with self.gateway.sendLock:
                request = {target_axis: 1}
                positive_limit = float(self.controller.qTRA(request)[target_axis])
                request = {target_axis: -1}
                negative_limit = float(self.controller.qTRA(request)[target_axis])

            if target_axis == "U" or target_axis == "V" or target_axis == "W":
                positive_limit = degrees_to_radians(positive_limit) 
                negative_limit = degrees_to_radians(negative_limit) 
        except Exception as ex:
            self.log.error("Failed to retrieve dynamic range for axis %s (%s)", target_axis, ex)
            dynamic_range =  (None, None)
        else:
            dynamic_range = (negative_limit, positive_limit)
            # self.log.info("Dynamic range queried for axis %s: %s", target_axis, dynamic_range)
        finally:
            # print(f"request: {request}. range: {dynamic_range}")
            return dynamic_range

    def get_compound_dynamic_range(self, target_axes:list, target_pose:list):
        """ Retrieve the dynamic range for a desired target pose given the current hexapod joint configuration. As the dynamic range is in general
        a function of both current configuration and target pose, this method returns the dynamic range of the hexapod as a function of both elements
        and also returns the computationally closest position to the target pose in case it's beyond the hexapod's reach. This results in different 
        dynamic ranges for the same current pose if different target poses are provided as arguments to the function

        Args:
            target_axes (list): axes that comprise the desired pose
            target_pose (list): values for each of the axes that comprise the target pose

        Returns:
            OrderedDict: ordered dictionary (native PI type) describing the range for each of the queried axes in the direction of the target pose
        """
        if (len(target_axes) != len(target_pose)):
            self.log.error("The amount of axes queried is not equal to the coordinates for target pose")
            return None
        
        try:
            params_dict = dict()
            for i, axis in enumerate(target_axes):
                params_dict[axis] = target_pose[i]
            with self.gateway.sendLock:
                dynamic_range = self.controller.qTRA(params_dict)

            if "U" in target_axes:
                dynamic_range["U"] = degrees_to_radians(dynamic_range["U"]) 
            if "V" in target_axes:
                dynamic_range["V"] = degrees_to_radians(dynamic_range["V"]) 
            if "W" in target_axes:
                dynamic_range["W"] = degrees_to_radians(dynamic_range["W"]) 

        except Exception as ex:
            self.log.error("Failed to retrieve the dynamic range for the request: %s (%s)", params_dict, ex)
            dynamic_range = None
        # else:
            # self.log.info("Dynamic range queried for compound pose %s: %s", params_dict, dynamic_range)
        finally:
            return dynamic_range


if __name__ == "__main__":
    hexapod = Hexapod("")
    hexapod.connect()
    hexapod.initialize()
    try:
        hexapod.get_status()
        hexapod.move_to_position_compound(0, 0, 0)
        position = hexapod.get_pose()
        # input()
        hexapod.move_to_angle_compound(0, 0, 10)
        time.sleep(3)
        hexapod.move_to_angle_compound(0, 0, 0)

    except Exception as ex:
        print("ERROR: %s", ex)
    finally:
        hexapod.disconnect()