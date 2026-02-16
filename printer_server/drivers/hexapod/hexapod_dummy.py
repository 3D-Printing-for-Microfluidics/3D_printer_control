
import time
import logging
from printer_server.logging_handler import dummy_log

from printer_server.drivers.generic_drivers import TTRStageDriver, FocusStageDriver
from printer_server.views.calibration import (
    get_last_calibration_positions_from_logs,
)

class Hexapod_dummy(TTRStageDriver, FocusStageDriver):
    def __init__(self, config_dict=None, log_level=logging.INFO):
        """ HexapodController

        Args:
            log_directory (str): root directory where the log file of this controller will be stored
        """
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.config_dict = config_dict

        self.connected = None
        self.initialized = False
        self.pose = {'X':0, 'Y':0, 'Z':0, 'U':0, 'V':0, 'W':0}
        self.pivot_point = {'R':0, 'S':0, 'T':0}
        self.axes = config_dict["axes"]
        self.axes_common_names = config_dict["axes_common_names"]

    @dummy_log
    def connect(self):
        """ Run routine for connecting to the hexapod and reference it if it hasn't been referenced yet upon powerup
        """
        self.connected = True

    def initialize(self):
        self.initialized = True

    @dummy_log
    def disconnect(self):
        """ Close connection to the hexapod
        """
        self.connected = None
        self.initialized = False

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
        # check if it has been referenced, else do referencing
        self.log.info("Referencing axes...")
        self.reference_axes()
        self.home_all_axes()
        calibration_positions = get_last_calibration_positions_from_logs()
        x = calibration_positions.get("pivot_x",0)/1000
        y = calibration_positions.get("pivot_y",0)/1000
        z = calibration_positions.get("pivot_z",0)/1000
        self.set_pivot_point(x,y,z)

    def getTTRPosition(self, axis=None, notify=True):
        return self.get_pose(self.convertAxis(axis))

    def absMoveTTR(self, rad=None, axis=None):
        self.move_to_angle_axis(self.convertAxis(axis), rad)

    def relMoveTTR(self, rad=None, axis=None):
        self.step_axis(self.convertAxis(axis), rad)

    def setup_log_file(self, filename):
        pass

    def logging_start(self):
        pass

    def logging_stop(self):
        pass

    def getDefaultFocusSpeed(self):
        return 0

    def getDefaultFocusAcceleration(self):
        return 0

    def getFocusPosition(self, notify=True):
        return self.get_pose("Focus")

    def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.move_to_position_axis(self.convertAxis("Focus"), mm)

    def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.step_axis(self.convertAxis("Focus"), mm)

    def startFocusJog(self, speed=None, acceleration=None):
        self.log.error("Hexapod Jogging not implemented")

    def stopFocusJog(self):
        self.log.error("Hexapod Jogging not implemented")

    ################################# End parent class functions #######################################

    @dummy_log
    def get_status(self):
        """ Retrieve any error codes from the hexapod

        Returns:
            int: error code
        """
        status = 0
        self.log.info("Querying hexapod error code number: %s", status)
        return status
    
    @dummy_log
    def reference_axes(self):
        """ Run routine for referencing all the axes of the hexapod
        """
        self.log.info("Referencing axes completed")

    @dummy_log    
    def home_all_axes(self):
        """ Home all the axes in the hexapod
        """
        self.pose = {'X':0, 'Y':0, 'Z':0, 'U':0, 'V':0, 'W':0}
        self.log.info("Homed all axes")

    @dummy_log
    def move_to_position_axis(self, axis, value):
        """ Perform absolute displacement of axis to target value

        Args:
            axis (str): which axis is being actuated (e.g. 'X', 'Y', or 'Z')
            value (float): target position in mm for the given axis
        """
        self.pose[axis] = value
        self.log.info("Translated axis %s to %s [mm]", axis, value)

    @dummy_log
    def move_to_position_compound(self, x, y, z):
        """ Perform absolute simultaneous translation of all translational axes to the specified positions in X, Y, and Z 

        Args:
            x (float): 'X' axis target position
            y (float): 'Y' axis target position
            z (float): 'Z' axis target position
        """
        self.pose['X'] = x
        self.pose['Y'] = y
        self.pose['Z'] = z
        self.log.info("Moved to position: (%s, %s, %s) mm", x, y, z)

    @dummy_log
    def move_to_angle_axis(self, axis, value):
        """ Perform absolute rotation of axes to the target value

        Args:
            axis (str): which axis is being actuated(e.g. 'U', 'V', or 'W')
            value (float): target position in rad for the given axis
        """
        self.pose[axis] = value
        self.log.info("Rotated axis %s to %s [rad]", axis, value)

    @dummy_log
    def move_to_angle_compound(self, u, v, w):
        """ Perform absolute simultaneous rotation of all rotational axes to the specified angles in U, V, and W

        Args:
            u (float): 'U' axis target angle
            v (float): 'V' axis target angle
            w (float): 'W' axis target angle
        """
        self.pose['U'] = u
        self.pose['V'] = v
        self.pose['W'] = w
        self.log.info("Moved to angle: (%s, %s, %s) rad", u, v, w)

    @dummy_log    
    def set_pose(self, x, y, z, u, v, w):
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
        self.pose['X'] = x
        self.pose['Y'] = y
        self.pose['Z'] = z
        self.pose['U'] = u
        self.pose['V'] = v
        self.pose['W'] = w
        self.log.info("Concurrently adjusted the pose to: 'X': %s, 'Y': %s, 'Z': %s, 'U': %s, 'V': %s, 'W': %s", x, y, z, u, v, w)

    @dummy_log
    def step_axis(self, axis, step_size):
        """ Perform relative actuation of the specified axis by the specified step size

        Args:
            axis (str): axis to be actuated (translated or rotated)
            step_size (float): step size of the translation or rotation of the specified axis
        """
        self.pose[axis] += step_size
        self.log.info("Stepped axis %s by %s", axis, step_size)

    @dummy_log
    def get_pose(self, axis=None):
        """ Get the current pose (translation and rotation) of the coordinate system corresponding to the current pivot point of the system

        Returns:
            list: values of the translational and rotational axes of the hexapod
        """
        if axis is None:
            return self.pose
        else:
            return self.pose[axis]

    @dummy_log
    def hard_stop(self):
        """ Stop any actuations within the hexapod currently beign executed
        """
        self.log.info("Motion stopped")

    @dummy_log
    def get_pivot_point(self):
        """ Retrieve the current pivot point

        Returns:
            OrderedDict: dictionary containing the axes and values of the pivot point
        """
        return self.pivot_point

    @dummy_log
    def set_pivot_point(self, r, s, t):
        """ Set the value of the pivot point about which the rotational commands are executed

        Args:
            r (float): 'R' axis target position (corresponding to the equivalent new coordinate system's 'X' axis)
            s (float): 'S' axis target position (corresponding to the equivalent new coordinate system's 'Y' axis)
            t (float): 'T' axis target position (corresponding to the equivalent new coordinate system's 'Z' axis)

        Returns:
            bool: successful change of pivot point
        """
        current_pose = self.get_pose()
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
            self.pivot_point['R'] = r
            self.pivot_point['S'] = s
            self.pivot_point['T'] = t
            return True
        else:
            self.log.warning("Not all rotational axes (U, V, W) are 0. Set them to 0 before attempting pivot point adjustment")
            return False

    @dummy_log    
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
        self.log.info("Pivot point stepped by %s on %s axis", step_size, axis)

    @dummy_log
    def get_simple_dynamic_range(self, target_axis:str):
        """ Get the range of motion of the requested axis. Due to the complexity of the hexapod joint configuration, dynamic ranges change if 
        multiple axis are actuated at once (which makes this type of query dependant on target pose), therefore for simplicity this dynamic 
        range query considers only the case where a single axis is actuated, making the computation independent on target pose (see)

        Args:
            target_axis_value (str): desired axis for dynamic range check (e.g. 'U', 'X', 'V', etc.)

        Returns:
            tuple: negative and positive ranges of the requested axis at the given pose
        """
        dynamic_range = (float('-inf'), float('inf'))
        return dynamic_range

    @dummy_log
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
            self.log.error("The amount of axes queried is not equal to the coordinates for target pose")
            return None
        
        dynamic_range = dict()
        for axis in target_axes:
            dynamic_range[axis] = self.get_simple_dynamic_range(axis)
        return dynamic_range


if __name__ == "__main__":
    hexapod = Hexapod_dummy("")
    hexapod.connect()
    hexapod.get_status()
    hexapod.move_to_position_compound(0, 0, 0)
    position = hexapod.get_pose()
    # input()
    hexapod.move_to_angle_compound(0, 0, 10)
    time.sleep(3)
    hexapod.move_to_angle_compound(0, 0, 0)
    hexapod.disconnect()