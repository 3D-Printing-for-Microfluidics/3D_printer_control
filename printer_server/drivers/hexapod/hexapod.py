import os
import time
import atexit
import logging
import traceback

from pipython import GCSDevice, pitools
from pipython.pidevice.gcscommands import GCSCommands
from pipython.pidevice.gcsmessages import GCSMessages
from pipython.pidevice.interfaces.pisocket import PISocket

from printer_server.drivers.generic_drivers import TTRStageDriver, FocusStageDriver

class Hexapod(TTRStageDriver, FocusStageDriver):
    def __init__(self, config_dict=None, log_level=logging.INFO):
        """ HexapodController

        Args:
            log_directory (str): root directory where the log file of this controller will be stored
        """
        super().__init__()
        
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.config_dict = config_dict
        self.connected = None
        self.initialized = False
        self.axes = config_dict["axes"]
        self.axes_common_names = config_dict["axes_common_names"]

    def connect(self, shutdown):
        """ Run routine for connecting to the hexapod and reference it if it hasn't been referenced yet upon powerup
        """
        if self.connected is None:
            self.connected = False
            try:    
                gateway = PISocket(host=self.config_dict["address"], port=self.config_dict["port"])
                messages = GCSMessages(gateway)
                self.controller = GCSCommands(gcsmessage=messages)
                self.connected = True
            except Exception as ex:
                # self.log.error(f"Failed to establish connection to the hexapod controller. Traceback: {traceback.print_exc()}")
                self.connected = None
                msg = f"Hexopod not found!"
                self.log.critical(msg)
                return False
                
            atexit.register(self.disconnect)
            self.log.info(f"Connected to hexapod controller")
            return True
        else:
            while self.connected is False:
                time.sleep(0.1)
        return None
    
    def initialize(self):
        # check if it has been referenced, else do referencing
        referenced_axes_flags = self.controller.qFRF() # ourput: referenced_axes_flags: OrderedDict([('X', True), ('Y', True), ('Z', True), ('U', True), ('V', True), ('W', True)])
        if False in referenced_axes_flags.values():
            self.reference_axes()
        self.initialized = True

    def disconnect(self):
        """ Close connection to the hexapod
        """
        if self.connected is not None and self.connected and self.socket is not None:
            self.connected = None
            self.initialized = False
            self.controller.CloseConnection()
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
        self.set_pivot_point(self.config_dict["pivot_x_mm"],self.config_dict["pivot_y_mm"],self.config_dict["pivot_z_mm"])

    def absMoveTTR(self, mdeg=None, axis=None):
        self.move_to_angle_axis(self.convertAxis(axis), mdeg/1000)

    def setup_log_file(self, filename):
        pass

    def logging_start(self):
        pass

    def logging_stop(self):
        pass

    def getFocusPosition(self, notify=True):
        return self.get_pose(self.convertAxis("Focus"))

    def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        # self.set_pivot_point(self.config_dict["pivot_x_mm"],self.config_dict["pivot_y_mm"],self.config_dict["pivot_z_mm"]-mm)
        self.move_to_position_axis(self.convertAxis("Focus"), mm)

    def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        # self.step_pivot_point("T", -mm)
        self.step_axis(self.convertAxis("Focus"), mm)

    def startFocusJog(self, speed=None, acceleration=None):
        self.log.error("Hexapod Jogging not implemented")

    def stopFocusJog(self):
        self.log.error("Hexapod Jogging not implemented")

    ################################# End parent class functions #######################################
        
    def get_status(self):
        """ Retrieve any error codes from the hexapod

        Returns:
            int: error code
        """
        status = self.controller.qERR()
        self.log.info(f"Querying hexapod error code number: {status}")
        return status

    def reference_axes(self):
        """ Run routine for referencing all the axes of the hexapod
        """
        self.log.info("Referencing axes...")
        self.controller.FRF()
        pitools.waitontarget(self.controller)
        self.log.info(f"Referencing axes completed")
    
    def home_all_axes(self):
        """ Home all the axes in the hexapod
        """
        self.log.info(f"Homing axes...")
        self.set_pose(0,0,0,0,0,0, suppress_message=True)
        self.log.info(f"Homing axes completed")

    def move_to_position_axis(self, axis, value):
        """ Perform absolute displacement of axis to target value

        Args:
            axis (str): which axis is being actuated (e.g. 'X', 'Y', or 'Z')
            value (float): target position in mm for the given axis
        """
        self.controller.MOV(axis, value)
        pitools.waitontarget(self.controller)
        self.log.info(f"Translated axis {axis} to {value} [mm]")

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
                self.log.warn(f"parameter provided is None. No motion performed")
                return

        self.controller.MOV({'X': x, 'Y': y, 'Z': z}, None) # Try this one out!

        pitools.waitontarget(self.controller)
        self.log.info(f"Moved to position: ({x}, {y}, {z})")

    def move_to_angle_axis(self, axis, value):
        """ Perform absolute rotation of axes to the target value

        Args:
            axis (str): which axis is being actuated(e.g. 'U', 'V', or 'W')
            value (float): target position in degrees for the given axis
        """
        self.controller.MOV(axis, value)
        pitools.waitontarget(self.controller)
        self.log.info(f"Rotated axis {axis} to {value} [degrees]")

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
                self.log.warn(f"parameter provided is None. No motion performed")
                return

        self.controller.MOV({'U': u, 'V': v, 'W': w}, None) # Try this one out!

        pitools.waitontarget(self.controller)
        self.log.info(f"Moved to angle: ({u}, {v}, {w})")
    
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
        self.controller.MOV({'X': x, 'Y': y, 'Z': z, 'U': u, 'V': v, 'W': w})
        pitools.waitontarget(self.controller)

        if not suppress_message:
            self.log.info(f"Concurrently adjusted the pose to: 'X': {x}, 'Y': {y}, 'Z': {z}, 'U': {u}, 'V': {v}, 'W': {w}")

    def step_axis(self, axis, step_size):
        """ Perform relative actuation of the specified axis by the specified step size

        Args:
            axis (str): axis to be actuated (translated or rotated)
            step_size (float): step size of the translation or rotation of the specified axis
        """
        self.controller.MVR(axis, step_size)
        pitools.waitontarget(self.controller)
        self.log.info(f"Stepped axis {axis} by {step_size}")

    def get_pose(self, axis=None):
        """ Get the current pose (translation and rotation) of the coordiante system corresponding to the current pivot point of the system

        Returns:
            list: values of the translational and rotational axes of the hexapod
        """
        if axis is None:
            positions_raw = self.controller.qPOS()
            return positions_raw
        else:
            a = self.convertAxis(axis)
            positions_raw = self.controller.qPOS(a)
            position = round(positions_raw[a],3)
            self.log.info(f"Get {axis}/{a} pos: {position}")
            return position

    def hard_stop(self):
        """ Stop any actuations within the hexapod currently beign executed
        """
        self.controller.STP()
        self.log.info("Motion stopped")

    def get_pivot_point(self):
        """ Retrieve the current pivot point

        Returns:
            OrderedDict: dictionary containing the axes and values of the pivot point
        """
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
            if axis >= 0.001:
                all_rotational_axes_zero = False
        if all_rotational_axes_zero:
            self.controller.SPI({'R': r, 'S': s, 'T': t})
            pitools.waitontarget(self.controller)
            ret_val = self.get_pivot_point()
            self.log.info(f"Pivot point set to: {ret_val['R']}, {ret_val['S']}, {ret_val['T']}")
            return True
        else:
            self.log.warning(f"Not all rotational axes (U, V, W) are 0. Set them to 0 before attempting pivot point adjustment")
            return False
    
    def step_pivot_point(self, axis, step_size):
        """ Move the pivot point by step_size relative to the current position

        Args:
            axis (str): pivot point axis (e.g. 'R', 'S'. or 'T')
            step_size (float): step size for moving the pivot point
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
        self.log.info(f"Pivot point stepped by {step_size} on {axis} axis")

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
            request = {target_axis: 1}
            positive_limit = float(self.controller.qTRA(request)[target_axis])
            request = {target_axis: -1}
            negative_limit = float(self.controller.qTRA(request)[target_axis])
        except Exception as ex:
            self.log.error(f"Failed to retrieve dynamic range for axis {target_axis}. Exception: {ex}")
            dynamic_range =  (None, None)
        else:
            dynamic_range = (negative_limit, positive_limit)
            # self.log.info(f"Dynamic range queried for axis {target_axis}: {dynamic_range}")
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
            OrderedDict: ordered dictionary (native PI type) describing the range for each of hte queried axes in the direction of the target pose
        """
        if (len(target_axes) != len(target_pose)):
            self.log.error(f"The amount of axes queried is not equal to the coordinates for target pose")
            return None
        
        try:
            params_dict = dict()
            for i, axis in enumerate(target_axes):
                params_dict[axis] = target_pose[i]
            dynamic_range = self.controller.qTRA(params_dict)
        except Exception as ex:
            self.log.error(f"Failed to retrieve the dynamic range for the request: {params_dict}")
            dynamic_range = None
        # else:
            # self.log.info(f"Dynamic range queried for compound pose {params_dict}: {dynamic_range}")
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
        print(f"ERROR: {ex}")
    finally:
        hexapod.disconnect()