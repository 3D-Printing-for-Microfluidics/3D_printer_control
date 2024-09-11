import re
import logging
from printer_server.drivers.generic_drivers import USBSerial, TTRStageDriver


class TipTilt(USBSerial, TTRStageDriver):
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__("Tiptilt", vid=config_dict["vendor_id"], pid=config_dict["product_id"], sn=config_dict["serial_number"], baudrate=config_dict["baudrate"], multiline=True, logger=self.log)

        self.config_dict = config_dict
        self.r = re.compile(r"\d*\.?\d*$")  # regex for getter functions
        self.initialized = None
        self.axes = config_dict["axes"]
        self.axes_common_names = config_dict["axes_common_names"]

    def convertAxis(self, axis):
        for i in range(len(self.axes)):
            if axis in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
            if axis.capitalize() in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
        raise ValueError("Invalid axis supplied")


    ################################# Parent class functions #######################################
    def getTTRPosition(self, axis=None, notify=True):
        return self.get_position(axis)

    def absMoveTTR(self, rad=None, axis=None):
        self.move_absolute(self, axis, rad, fast=False)

    def relMoveTTR(self, rad=None, axis=None):
        self.move_relative(self, axis, rad, fast=False)

    def setup_log_file(self, filename):
        pass

    def logging_start(self):
        pass

    def logging_stop(self):
        pass

    ################################# End parent class functions #######################################

    ## wrappers for commands from Teensyduino ##

    # returns "Done"
    def initialize(self):
        self.initialized = False
        self.log.info("Initializing TipTilt...")
        r = self.send("IN0")
        self.log.info("Initialized TipTilt")
        self.initialized = True
        return r

    # returns "Done" or "Error"
    def home(self):
        self.log.info("Homing TipTilt...")
        r = self.send("HM0")
        self.log.info("Homed TipTilt")
        return r

    # returns "Done"
    def reset(self):
        return self.send("RS0")

    # returns a float
    def get_position(self, axis):
        position = self.send(f"GP{self.convertAxis(axis)}", parse_float_at_index=0)
        if position == 12345:
            return "undef"
        else:
            return position

    # returns a float
    def get_min_position(self, axis):
        return self.send(f"GL{self.convertAxis(axis)}", parse_float_at_index=0)

    # returns a float
    def get_max_position(self, axis):
        return self.send(f"GU{self.convertAxis(axis)}", parse_float_at_index=0)

    # returns an int
    def get_acceleration(self, axis):
        return self.send(f"GA{self.convertAxis(axis)}", parse_float_at_index=0)

    # returns "Done"
    def set_acceleration(self, axis, acceleration):
        return self.send(f"SA{self.convertAxis(axis)} {acceleration}")

    # returns an int
    def get_speed(self, axis):
        return self.send(f"GV{self.convertAxis(axis)}", parse_float_at_index=0)

    # returns "Done"
    def set_speed(self, axis, acceleration):
        return self.send(f"SV{self.convertAxis(axis)} {acceleration}")

    # returns "Done" or "Error"
    def move_relative(self, axis, distance_um, fast=False):
        self.log.info("Moving %s by %s um", axis, distance_um)
        if fast:  # coarse mode uses less precise positioning for quicker moves
            return self.send(f"Mr{self.convertAxis(axis)} {distance_um}")
        return self.send(f"MR{self.convertAxis(axis)} {distance_um}")

    # returns "Done" or "Error"
    def move_absolute(self, axis, distance_um, fast=False):
        self.log.info("Moving %s to %s um", axis, distance_um)
        if fast:  # coarse mode uses less precise positioning for quicker moves
            return self.send(f"Ma{self.convertAxis(axis)} {distance_um}")
        return self.send(f"MA{self.convertAxis(axis)} {distance_um}")

    # wrapper to plug into existing calibration threads interface
    def move(self, axis, distance_um, relative=True, fast=False):
        """
        Move the specified number of um at the specified speed (in mm/min)
        """
        if relative:
            return self.move_relative(axis, distance_um, fast)
        else:
            return self.move_absolute(axis, distance_um, fast)


if __name__ == "__main__":
    t = TipTilt()
    t.connect(exit)
    # t.home()
    print(f"{t.get_position('Tip')}")
    print(f"{t.get_position('Tilt')}")
