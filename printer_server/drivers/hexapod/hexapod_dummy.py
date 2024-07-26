
import time
from printer_server.logging_handler import dummy_log

class Hexapod_dummy:
    def __init__(self):
        """ HexapodController

        Args:
            log_directory (str): root directory where the log file of this controller will be stored
        """
        self.initialized = False
        self.referenced  = False
        self.pose = {'X':0, 'Y':0, 'Z':0, 'U':0, 'V':0, 'W':0}
        self.pivot_point = {'R':0, 'S':0, 'T':0}

    @dummy_log
    def check_initialization(self):
        """ Check if the hexapod controller has been initialized

        Returns:
            bool: flag for whether the hexapod has been initialized or not
        """
        return self.initialized

    @dummy_log
    def connect(self):
        """ Run routine for connecting to the hexapod and reference it if it hasn't been referenced yet upon powerup
        """
        self.logging_handle.info(f"Connected to hexapod controller")
        self.initialized = True

    @dummy_log
    def reference_axes(self):
        """ Run routine for referencing all the axes of the hexapod
        """
        self.referenced = True
        self.logging_handle.info(f"Referencing axes completed")

    @dummy_log
    def close(self):
        """ Close connection to the hexapod
        """
        self.logging_handle.info("Connection closed")

    @dummy_log
    def get_status(self):
        """ Retrieve any error codes from the hexapod

        Returns:
            int: error code
        """
        status = 0
        self.logging_handle.info(f"Querying hexapod error code number: {status}")
        return status

    @dummy_log    
    def home_all_axes(self):
        """ Home all the axes in the hexapod
        """
        self.pose = {'X':0, 'Y':0, 'Z':0, 'U':0, 'V':0, 'W':0}
        self.logging_handle.info(f"Homed all axes")

    @dummy_log
    def move_to_position_axis(self, axis, value):
        """ Perform absolute displacement of axis to target value

        Args:
            axis (str): which axis is being actuated (e.g. 'X', 'Y', or 'Z')
            value (float): target position in mm for the given axis
        """
        try:
            self.pose[axis] = value
        except Exception as ex:
            self.logging_handle.error(f"Failed to move axis {axis} to {value}. {ex}")
        else:
            self.logging_handle.info(f"Translated axis {axis} to {value} [mm]")

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
        self.logging_handle.info(f"Moved to position: ({x}, {y}, {z})")

    @dummy_log
    def move_to_angle_axis(self, axis, value):
        """ Perform absolute rotation of axes to the target value

        Args:
            axis (str): which axis is being actuated(e.g. 'U', 'V', or 'W')
            value (float): target position in degrees for the given axis
        """
        try:
            self.pose[axis] = value
        except Exception as ex:
            self.logging_handle.error(f"Failed to rotate axis {axis} to {value}. {ex}")
        else:
            self.logging_handle.info(f"Rotated axis {axis} to {value} [degrees]")

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
        self.logging_handle.info(f"Moved to angle: ({u}, {v}, {w})")

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
        self.logging_handle.info(f"Concurrently adjusted the pose to: \n\t* Translation- 'X': {x}, 'Y': {y}, 'Z': {z}\n\t* Rotation- 'U': {u}, 'V': {v}, 'W': {w}")

    @dummy_log
    def step_axis(self, axis, step_size):
        """ Perform relative actuation of the specified axis by the specified step size

        Args:
            axis (str): axis to be actuated (translated or rotated)
            step_size (float): step size of the translation or rotation of the specified axis
        """
        self.pose[axis] += step_size
        self.logging_handle.info(f"Stepped axis {axis} by {step_size}")

    @dummy_log
    def get_pose(self):
        """ Get the current pose (translation and rotation) of the coordiante system corresponding to the current pivot point of the system

        Returns:
            list: values of the translational and rotational axes of the hexapod
        """
        pose_list = [self.pose['X'], self.pose['Y'], self.pose['Z'], self.pose['U'], self.pose['V'], self.pose['W']]
        return pose_list

    @dummy_log
    def hard_stop(self):
        """ Stop any actuations within the hexapod currently beign executed
        """
        self.logging_handle.info("Motion stopped")

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
            r (float): 'R' axis target position (corresponding to the equivalent new coordiante system's 'X' axis)
            s (float): 'S' axis target position (corresponding to the equivalent new coordiante system's 'Y' axis)
            t (float): 'T' axis target position (corresponding to the equivalent new coordiante system's 'Z' axis)

        Returns:
            bool: successful change of pivot point
        """
        current_pose = self.get_pose()
        rotational_axes = current_pose[3:]
        all_rotational_axes_zero = True
        for axis in rotational_axes:
            if axis != 0.0:
                all_rotational_axes_zero = False
        if all_rotational_axes_zero:
            self.pivot_point['R'] = r
            self.pivot_point['S'] = s
            self.pivot_point['T'] = t
            return True
        else:
            self.logging_handle.warning(f"Not all rotational axes (U, V, W) are 0. Set them to 0 before attempting pivot point adjustment")
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
        self.logging_handle.info(f"Pivot point stepped by {step_size} on {axis} axis")

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
            self.logging_handle.error(f"The amount of axes queried is not equal to the coordinates for target pose")
            return None
        
        dynamic_range = dict()
        try:
            for axis in target_axes:
                dynamic_range[axis] = self.get_simple_dynamic_range(axis)
        except Exception as ex:
            self.logging_handle.error(f"Failed to retrieve the dynamic range for the target_axes: {target_axes}, and target_pose: {target_pose}")
            dynamic_range = None
        finally:
            return dynamic_range


if __name__ == "__main__":
    hexapod = Hexapod_dummy("")
    hexapod.connect()
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
        hexapod.close()