from pipython import GCSDevice, pitools
from pipython.pidevice.gcscommands import GCSCommands
from pipython.pidevice.gcsmessages import GCSMessages
from pipython.pidevice.interfaces.pisocket import PISocket
import time
import logging
import os
import traceback

CONTROLLER_IP_ADDRESS = '192.168.0.6' # '172.16.244.33'
CONTROLLER_PORT = 50000
CONTROLLER_NAME = 'C-887'

WINDOWS_OS = "nt"
LINUX_OS = "posix"

class Hexapod:
    def __init__(self, log_directory, log_level=logging.INFO, controller_ip=CONTROLLER_IP_ADDRESS, controller_port=CONTROLLER_PORT):
        """ HexapodController

        Args:
            log_directory (str): root directory where the log file of this controller will be stored
        """
        self.initialized = False
        self.initialize_logs(log_directory, log_level)
        self.os = os.name
        self.controller_ip = controller_ip
        self.controller_port = controller_port

    def check_initialization(self):
        """ Check if the hexapod controller has been initialized

        Returns:
            bool: flag for whether the hexapod has been initialized or not
        """
        return self.initialized

    def connect(self):
        """ Run routine for connecting to the hexapod and reference it if it hasn't been referenced yet upon powerup
        """
        os_used = ""
        try:
            if (self.os == WINDOWS_OS):
                self.controller = GCSDevice()
                self.controller.InterfaceSetupDlg()  # Opens a dialog to set up the connection
                pitools.startup(self.controller)
                os_used = "Windows"
                
            elif (self.os == LINUX_OS):
                gateway = PISocket(host=self.controller_ip, port=self.controller_port)
                messages = GCSMessages(gateway)
                self.controller = GCSCommands(gcsmessage=messages)
                os_used = "Linux"

        except Exception as ex:
            self.logging_handle.error(f"Failed to establish connection to the hexapod controller. Traceback: {traceback.print_exc()}")
            self.initialized = False
            
        else:
            self.logging_handle.info(f"Connected to hexapod controller on {os_used} OS platform")

            # check if it has been referenced, else do referencing
            referenced_axes_flags = self.controller.qFRF() # ourput: referenced_axes_flags: OrderedDict([('X', True), ('Y', True), ('Z', True), ('U', True), ('V', True), ('W', True)])
        
            if False in referenced_axes_flags.values():
                self.logging_handle.info("Referencing axes...")
                self.reference_axes()
            
            self.initialized = True

    def reference_axes(self):
        """ Run routine for referencing all the axes of the hexapod
        """
        self.controller.FRF()
        pitools.waitontarget(self.controller)
        self.logging_handle.info(f"Referencing axes completed")

    def close(self):
        """ Close connection to the hexapod
        """
        self.controller.CloseConnection()
        self.logging_handle.info("Connection closed")

    def initialize_logs(self, log_directory, log_level):
        """ Initialize log handle

        Args:
            log_directory (str): directory where the log handle will store the log file
        """
        # Initialize the logging info format
        self.logging_handle = logging.getLogger(__name__)
        self.logging_handle.setLevel(log_level)

        # File handler
        self.log_local_directory = log_directory
        file_name = __name__.split(".")[-1]
        log_file_name = f"{file_name}.log"
        full_log_file_name = os.path.join(log_directory, log_file_name)
        file_handler = logging.FileHandler(full_log_file_name, mode="w") 

        # Format log entries
        file_formatter  = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter) 

        # Format console entries
        stream_formatter = logging.Formatter(f'%(asctime)s - {file_name} - %(levelname)s - %(message)s')
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(stream_formatter)

        # Add handlers to logger
        self.logging_handle.addHandler(file_handler) 
        self.logging_handle.addHandler(stream_handler)

        # Info message of log initialization
        self.logging_handle.info("Microfluidic Testing Control Logger initialized")

    def get_status(self):
        """ Retrieve any error codes from the hexapod

        Returns:
            int: error code
        """
        status = self.controller.qERR()
        self.logging_handle.info(f"Querying hexapod error code number: {status}")
        return status
    
    def home_all_axes(self):
        """ Home all the axes in the hexapod
        """
        self.controller.GOH()
        pitools.waitontarget(self.controller)
        self.logging_handle.info(f"Homed all axes")

    def move_to_position_axis(self, axis, value):
        """ Perform absolute displacement of axis to target value

        Args:
            axis (str): which axis is being actuated (e.g. 'X', 'Y', or 'Z')
            value (float): target position in mm for the given axis
        """
        self.controller.MOV(axis, value)
        pitools.waitontarget(self.controller)
        self.logging_handle.info(f"Translated axis {axis} to {value} [mm]")

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
                self.logging_handle.info(f"parameter provided is None. No motion performed")
                return

        self.controller.MOV({'X': x, 'Y': y, 'Z': z}, None) # Try this one out!

        pitools.waitontarget(self.controller)
        self.logging_handle.info(f"Moved to position: ({x}, {y}, {z})")

    def move_to_angle_axis(self, axis, value):
        """ Perform absolute rotation of axes to the target value

        Args:
            axis (str): which axis is being actuated(e.g. 'U', 'V', or 'W')
            value (float): target position in degrees for the given axis
        """
        self.controller.MOV(axis, value)
        pitools.waitontarget(self.controller)
        self.logging_handle.info(f"Rotated axis {axis} to {value} [degrees]")

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
                self.logging_handle.info(f"parameter provided is None. No motion performed")
                return

        self.controller.MOV({'U': u, 'V': v, 'W': w}, None) # Try this one out!

        pitools.waitontarget(self.controller)
        self.logging_handle.info(f"Moved to angle: ({u}, {v}, {w})")
    
    def set_pose(self, x, y, z, u, v, w):
        """ Perform absolute simultaneous translation and rotation of all translational and rotational axes to the specified positions and angles in X, Y, Z, U, V, and W to specify the pose of the coordinate system that corresponds to the current pivot point

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

        self.logging_handle.info(f"Concurrently adjusted the pose to: \n\t* Translation- 'X': {x}, 'Y': {y}, 'Z': {z}\n\t* Rotation- 'U': {u}, 'V': {v}, 'W': {w}")

    def step_axis(self, axis, step_size):
        """ Perform relative actuation of the specified axis by the specified step size

        Args:
            axis (str): axis to be actuated (translated or rotated)
            step_size (float): step size of the translation or rotation of the specified axis
        """
        self.controller.MVR(axis, step_size)
        pitools.waitontarget(self.controller)
        self.logging_handle.info(f"Stepped axis {axis} by {step_size}")

    def get_pose(self):
        """ Get the current pose (translation and rotation) of the coordiante system corresponding to the current pivot point of the system

        Returns:
            list: values of the translational and rotational axes of the hexapod
        """
        positions_raw = self.controller.qPOS()
        positions = [round(list(positions_raw.values())[0], 1), 
                     round(list(positions_raw.values())[1], 1), 
                     round(list(positions_raw.values())[2], 1), 
                     round(list(positions_raw.values())[3], 1), 
                     round(list(positions_raw.values())[4], 1), 
                     round(list(positions_raw.values())[5], 1)]
        self.logging_handle.info(f"Current pose: {positions}")
        return positions

    def hard_stop(self):
        """ Stop any actuations within the hexapod currently beign executed
        """
        self.controller.STP()
        self.logging_handle.info("Motion stopped")

    def get_pivot_point(self):
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
        rotational_axes = current_pose[3:]
        all_rotational_axes_zero = True
        for axis in rotational_axes:
            if axis != 0.0:
                all_rotational_axes_zero = False
        if all_rotational_axes_zero:
            self.controller.SPI({'R': r, 'S': s, 'T': t})
            pitools.waitontarget(self.controller)
            ret_val = self.get_pivot_point()
            self.logging_handle.info(f"Pivot point set to: {ret_val}")
            return True
        else:
            self.logging_handle.info(f"Not all rotational axes (U, V, W) are 0. Set them to 0 before attempting pivot point adjustment")
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
        self.logging_handle.info(f"Pivot point stepped by {step_size} on {axis} axis")

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
            self.logging_handle.error(f"Failed to retrieve dynamic range for axis {target_axis}. Exception: {ex}")
            dynamic_range =  (None, None)
        else:
            dynamic_range = (negative_limit, positive_limit)
            self.logging_handle.info(f"Dynamic range queried for axis {target_axis}: {dynamic_range}")
        finally:
            print(f"request: {request}. range: {dynamic_range}")
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
            self.logging_handle.error(f"The amount of axes queried is not equal to the coordinates for target pose")
            return None
        
        try:
            params_dict = dict()
            for i, axis in enumerate(target_axes):
                params_dict[axis] = target_pose[i]
            dynamic_range = self.controller.qTRA(params_dict)
        except Exception as ex:
            self.logging_handle.error(f"Failed to retrieve the dynamic range for the request: {params_dict}")
            dynamic_range = None
        else:
            self.logging_handle.info(f"Dynamic range queried for compound pose {params_dict}: {dynamic_range}")
        finally:
            return dynamic_range


if __name__ == "__main__":
    hexapod = Hexapod("")
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