import re
import time
import logging
from pathlib import Path
from datetime import datetime
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.drivers.generic_drivers import USBSerial, TTRStageDriver


class TipTilt(USBSerial, TTRStageDriver):
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__("Tiptilt", vid=config_dict["vendor_id"], pid=config_dict["product_id"], sn=config_dict["serial_number"], baudrate=config_dict["baudrate"], multiline=True, logger=self.log)

        self.thread = Thread(self.log, name="tiptilt_loop_thread", target=self.loop)
        self.thread.daemon = True
        self.thread_running = False
        self.logging_running = False

        self.config_dict = config_dict
        self.movement_log = None
        self.r = re.compile(r"\d*\.?\d*$")  # regex for getter functions
        self.initialized = None
        self.axes = config_dict["axes"]
        self.axes_common_names = config_dict["axes_common_names"]
        self.limits = config_dict["limits"]

    def convertAxis(self, axis):
        for i in range(len(self.axes)):
            if axis in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
            if axis.capitalize() in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
        raise ValueError(f"Invalid axis supplied: {axis}")


    ################################# Parent class functions #######################################
    def getTTRPosition(self, axis=None, notify=True):
        return self.get_position(axis)

    def absMoveTTR(self, rad=None, axis=None):
        self.move_absolute(axis, rad, fast=False)

    def relMoveTTR(self, rad=None, axis=None):
        self.move_relative(axis, rad, fast=False)

    def getTTRLimits(self, axis=None):
        return self.getSoftwareLimits(axis)
    
    def setTTRLimits(self, limits=None, axis=None):
        a = self.convertAxis(axis)
        if limits is None:
            limits = self.limits[a]
        if limits[0] is not None:
            self.setLowerLimit(limits[0], axis=axis)
        if limits[1] is not None:
            self.setUpperLimit(limits[1], axis=axis)

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
            self.movement_log = str(Path(filename) / "tiptilt_movement_data.csv")
            async_file_hander.write(self.movement_log, "timestamp,")
            for a in self.axes_common_names:
                async_file_hander.write(self.movement_log, f"{a} position_rad,")
            async_file_hander.write(self.movement_log, "\n")
        elif self.movement_log is not None and filename is None:
            self.movement_log = None

    def logging_start(self):
        """
        Starts collecting position data
        """
        if not self.logging_running:
            self.logging_running = True
            self.log.info("TT logging started")

    def logging_stop(self):
        """
        Stops collecting position data
        """
        if self.logging_running:
            self.logging_running = False
            self.log.info("TT logging stopped")

    def loop(self):
        try:
            while self.thread_running:
                if self.logging_running:
                    if self.movement_log is not None:
                        tmp = ""
                        for a in self.axes:
                            tmp += f"{self.get_position(a)},"
                        self.write_to_disk(tmp)
                time.sleep(0.1)
        except Exception as ex:
            self.log.warning("TT loop failed (%s)", ex, exc_info=True)
            self.thread_running = False

    ################################# End parent class functions #######################################

    ## wrappers for commands from Teensyduino ##

    # returns "Done"
    def initialize(self):
        self.initialized = False
        self.log.info("Initializing TipTilt...")
        r = self.send("IN0")
        self.log.info("Initialized TipTilt")
        self.initialized = True

        self.thread_running = True
        self.thread.start()
        return r
    
    def disconnect(self):
        if self.thread_running:
            self.thread_running = False
            self.thread.join()
            self.thread = Thread(self.log, name="tiptilt_loop_thread", target=self.loop)
            self.thread.daemon = True
        super().disconnect()

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
        
    def getSoftwareLimits(self, axis=None):
        a = self.convertAxis(axis)
        ll = self.send(f"GL{a}", parse_float_at_index=0)
        ul = self.send(f"GU{a}", parse_float_at_index=0)
        return (ll, ul)

    def setLowerLimit(self, limit, axis=None):
        self.log.warn("Setting limits not implemented")

    def setUpperLimit(self, limit, axis=None):
        self.log.warn("Setting limits not implemented")

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
