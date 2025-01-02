# Based on https://www.thorlabs.com/Software/Motion%20Control/APT_Communications_Protocol_v38.pdf

import time
import atexit
import logging
import threading
from pathlib import Path
from datetime import datetime
from struct import pack, unpack
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.drivers.generic_drivers import USBSerial, FocusStageDriver, TTRStageDriver

MODULE_IDENT_CMD = 0x0223
MODULE_ENABLE_SET = 0x0210
HW_DISCONNECT_CMD = 0x0002
HW_START_STATUS_CMD = 0x0011
HW_STOP_STATUS_CMD = 0x0012
HW_INFO_GET = 0x0005
HUB_BAYUSED_GET = 0x0065
POS_GET = 0x0411
VEL_ACC_SET = 0x0413
VEL_ACC_GET = 0x0414
LIMITS_SET = 0x0423
LIMITS_GET = 0x0424
HOME_CMD = 0x0443
MOV_REL_CMD = 0x0448
MOV_ABS_CMD = 0x0453
MOV_VEL_CMD = 0x0457
MOV_STOP_CMD = 0x0465
UPDATE_GET = 0x0490
UPDATE_ACK = 0x0492
T = 2048 / (6*10**6)


RSPS = {
    "HW_ERROR_RSP": 0x0081,
    "HW_INFO_RSP": 0x0006,
    "HUB_BAYUSED_RSP": 0x0066,
    "POS_RSP": 0x0412,
    "VEL_ACC_RSP": 0x0415,
    "LIMITS_RSP": 0x0425,
    "HOME_RSP": 0x0444,
    "MOV_RSP": 0x0464,
    "MOV_STOP_RSP": 0x0466,
    "UPDATE_RSP": 0x0491
}

class KDC101(USBSerial, FocusStageDriver): # TTRStageDriver
    def __init__(
        self,
        config_dict=None,
        log_level=logging.DEBUG,
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.movement_log = None
        self.config_dict = config_dict

        super().__init__("KDC101", vid=config_dict["vendor_id"], pid=config_dict["product_id"], baudrate=config_dict["baudrate"], timeout=0.25, logger=self.log)

        self.sendLock = threading.Lock()

        self.thread = Thread(self.log, name="kdc_loop_thread", target=self.loop)
        self.thread.daemon = True
        self.thread_running = False
        self.logging_running = False

        self.default_axis = config_dict["default_axis"]
        self.axes = config_dict["axes"]
        self.axes_common_names = config_dict["axes_common_names"]
        self.max_travel_mm = config_dict["axes_travel"]
        self.ctspmm = config_dict["axes_ctspmm"]
        self.default_speed = config_dict["axes_speed"]
        self.default_acceleration = config_dict["axes_acceleration"]
        self.limits = config_dict["limits"]

        self.channel = 1
        self.source = 0x01

        self.homed = {}
        self.moving = {}
        self.jogging = {}
        self.speed = {}
        self.acceleration = {}
        self.pre_jog_speed = {}
        self.pre_jog_acceleration = {}
        self.current_position = {}
        self.limit_array = {}
        for a in self.axes:
            self.homed[a] = False
            self.moving[a] = False
            self.jogging[a] = False
            self.speed[a] = 0
            self.acceleration[a] = 0
            self.pre_jog_speed[a] = 0
            self.pre_jog_acceleration[a] = 0
            self.current_position[a] = 0
            self.limit_array[a] = []

        # self.connected = None
        self.initialized = None

    def getCommonName(self, axis):
        if axis is None:
            axis = self.default_axis
        elif type(axis) is int:
            axis =  str(hex(axis))
        for i in range(len(self.axes)):
            if axis in (self.axes[i], self.axes_common_names[i]):
                return self.axes_common_names[i]
            if axis.upper() in (self.axes[i], self.axes_common_names[i]):
                return self.axes_common_names[i]
            if axis.lower() in (self.axes[i], self.axes_common_names[i]):
                return self.axes_common_names[i]
        raise ValueError("Invalid axis supplied")

    def convertAxis(self, axis=None):
        """Return converted axis name (eg. maps X,Y,Z to A,B,C)"""
        if axis is None:
            axis = self.default_axis
        elif type(axis) is int:
            return str(hex(axis)).lower()
        for i in range(len(self.axes)):
            if axis in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
            if axis.upper() in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
            if axis.lower() in (self.axes[i], self.axes_common_names[i]):
                return self.axes[i]
        raise ValueError("Invalid axis supplied")
    

    def getDefaultSpeed(self, axis=None):
        a = self.convertAxis(axis)
        return self.default_speed[a]

    def getDefaultAcceleration(self, axis=None):
        a = self.convertAxis(axis)
        return self.default_acceleration[a]

    def initialize(self):
        self.thread_running = True
        self.thread.start()
        
        for axis in self.axes:
            a = self.convertAxis(axis)
            self.getHardwareInfo(axis=a)
            time.sleep(0.25)
            self.motorOn(axis=a)
            time.sleep(0.25)
            self.write_to_KDC101(VEL_ACC_GET, self.channel, 0x00, a)
            time.sleep(0.25)
            self.write_to_KDC101(LIMITS_GET, self.channel, 0x00, a)
            time.sleep(0.25)
            # self.write_to_KDC101(UPDATE_GET, self.channel, 0x00, a)
            self.write_to_KDC101(HW_START_STATUS_CMD, 0x00, 0x00, a)
            time.sleep(0.25)

    def disconnect(self):
        if self.connected is not None and self.connected is not False:
            self.thread_running = False
            try:
                self.thread.join()
                self.thread = Thread(self.log, name="kdc_loop_thread", target=self.loop)
                self.thread.daemon = True

                for axis in self.axes:
                    a = self.convertAxis(axis)
                    self.motorOff(axis=a)
                    self.write_to_KDC101(HW_STOP_STATUS_CMD, 0x00, 0x00, a)
                    self.write_to_KDC101(HW_DISCONNECT_CMD, 0x00, 0x00, a)
            except:
                pass
        super().disconnect()

    def getHardwareInfo(self, axis=None):
        # Get HW info; MGMSG_HW_REQ_INFO; may be require by a K Cube to
        #  allow confirmation Rx messages
        a = self.convertAxis(axis)
        self.write_to_KDC101(HW_INFO_GET, 0x00, 0x00, a)

    # def sendServerAlive(self, axis=None):
    #     a = self.convertAxis(axis)
    #     self.write_to_KDC101(UPDATE_ACK, 0x00, 0x00, a)
    
    def write_to_disk(self, *args):
        """Write data to disk using the async file handler class.

        Log location must be set for data to be saved.
        """
        ts = "%Y-%m-%d %H:%M:%S.%f"
        async_file_hander.write(self.movement_log, datetime.now().strftime(ts) + ",")
        async_file_hander.write(self.movement_log, ",".join(map(str, args)) + "\n")

    def mmToCnts(self, mm, axis=None):
        """Convert mm to counts for the specified axis."""
        a = self.convertAxis(axis)
        return int(mm * self.ctspmm[a])

    def cntsToMm(self, counts, axis=None):
        """Convert counts to mm for the specified axis."""
        a = self.convertAxis(axis)
        return counts / self.ctspmm[a]
    
    def velToCnts(self, vel, axis=None):
        a = self.convertAxis(axis)
        return int(vel*(self.ctspmm[a]*65536*T))

    def cntsToVel(self, counts, axis=None):
        a = self.convertAxis(axis)
        return counts/(self.ctspmm[a]*65536*T)

    def accToCnts(self, acc, axis=None):
        a = self.convertAxis(axis)
        return int(acc*(self.ctspmm[a]*65536*T**2))

    def cntsToAcc(self, counts, axis=None):
        a = self.convertAxis(axis)
        return counts/(self.ctspmm[a]*65536*T**2)

    def write_to_KDC101(self, cmd, a, b, dest):
        with self.sendLock:
            msg = pack(f"<H4B", cmd, a, b, int(dest,16), 0x01)
            self.log.debug("Sent : '%s'", msg)
            self.write_bytes(msg)
    
    def long_write_to_KDC101(self, cmd, dest, extra_format, extra_data, extra_len):
        with self.sendLock:
            msg = pack(f"<2H2B{extra_format}", cmd, extra_len, int(dest,16)|0x80, 0x01, *extra_data)
            self.log.debug("Sent : '%s'", msg)
            self.write_bytes(msg)

    def parse_position(self, pos, axis=None):
        a = self.convertAxis(axis)
        getpos = self.cntsToMm(pos, axis=a)

        if not self.homed[a]:
            pos = "undef"

        if int(getpos) == 33400:
            pos = "undef"
        elif int(getpos) == 125203:
            pos = 0.0
        else:
            pos = round(
            getpos, 4
        )
            
        return pos

    def loop(self):
        while self.thread_running:
            if self.in_waiting >= 6:
                rsp = self.read_bytes(6)
                cmd, a, b, dest, source = unpack("<H4B", rsp)
                has_extra_bytes = (dest & 0x80) > 0
                if has_extra_bytes:
                    count = unpack("<H", pack("<BB", a, b))[0]
                    extra_bytes = self.read_bytes(count)
                dest &= 0x7F

                axis = self.convertAxis(source)
            
                if cmd == RSPS["HW_ERROR_RSP"]:
                    ident, code, error, _ = unpack("<HH63sB", extra_bytes)
                    self.log.warning("KDC %s error %s (%s)", source, code, error.rstrip().decode('utf-8'))

                elif cmd == RSPS["HW_INFO_RSP"]:
                    serial, model, type, firm_ver, _, hw_ver, mod_ver, nchs = unpack("<i8sH4s60s3H", extra_bytes)
                    self.log.debug("KDC %s hardware info: serial %s, model %s, type %s, fw ver %s, hw ver %s, mod %s, nchs %s", 
                                   source, serial, model, type, firm_ver, hw_ver, mod_ver, nchs)

                elif cmd == RSPS["HUB_BAYUSED_RSP"]:
                    if a == -0x01: # standalone
                        bay = None
                    elif a == 0x00: # unknown
                        bay = -1
                    else: # in bay x
                        bay = a
                    self.log.debug("KDC %s in bay %s (%s)", source, a, bay)

                elif cmd == RSPS["POS_RSP"]:
                    channel, pos = unpack("<Hi", extra_bytes)
                    self.current_position[axis] = self.parse_position(pos)
                    self.log.debug("KDC %s at %s", source, self.current_position[axis])

                elif cmd == RSPS["VEL_ACC_RSP"]:
                    channel, _, acc, speed = unpack("<Hiii", extra_bytes)
                    self.speed[axis] = self.cntsToVel(speed, axis=axis)
                    self.acceleration[axis] = self.cntsToAcc(acc, axis=axis)
                    self.log.debug("KDC %s speed:%s acc:%s", source, self.speed[axis], self.acceleration[axis])

                elif cmd == RSPS["LIMITS_RSP"]:
                    channel, upper_mode, lower_mode, upper_soft, lower_soft, soft_mode = unpack("<HHHiiH", extra_bytes)
                    self.limit_array[axis] = [upper_mode, lower_mode, upper_soft, lower_soft, soft_mode]
                    self.log.debug("KDC %s limit: upper hard %s lower hard %s, upper soft %s, lower soft %s, soft mode %s",
                                      source, upper_mode, lower_mode, self.cntsToMm(upper_soft, axis=axis), 
                                      self.cntsToMm(lower_soft, axis=axis), soft_mode)

                elif cmd == RSPS["HOME_RSP"]:
                    # channel = a
                    self.homed[axis] = True
                    self.log.debug("KDC %s homed", source)

                elif cmd == RSPS["MOV_RSP"] or cmd == RSPS["MOV_STOP_RSP"] or cmd == RSPS["UPDATE_RSP"]:
                    channel, pos, speed, current, status = unpack("<HiHHI", extra_bytes)
                    upper_hard_limit = (status & 0x1) > 0
                    lower_hard_limit = (status & 0x2) > 0
                    upper_soft_limit = (status & 0x4) > 0
                    lower_soft_limit = (status & 0x8) > 0
                    in_motion_pos = (status & 0x10) > 0
                    in_motion_neg = (status & 0x20) > 0
                    jogging_pos = (status & 0x40) > 0
                    jogging_neg = (status & 0x80) > 0
                    connected = (status & 0x100) > 0
                    homing = (status & 0x200) > 0
                    homed = (status & 0x400) > 0
                    position_error = (status & 0x4000) > 0
                    error = (status & 0x40000000) > 0
                    enabled = (status & 0x80000000) > 0
                    # self.sendServerAlive(axis=a)
                    self.log.debug("KDC %s update: pos %s, speed %s, upper_hard_limit %s, lower_hard_limit %s, upper_soft_limit %s, \
                                   lower_soft_limit %s, in_motion_pos %s, in_motion_neg %s, jogging_pos %s, jogging_neg %s, connected %s, \
                                   homing %s, homed %s, pos_error %s, error %s, enabled %s", self.parse_position(pos), 
                                   self.cntsToVel(speed, axis=axis), upper_hard_limit, lower_hard_limit, upper_soft_limit, lower_soft_limit, 
                                   in_motion_pos, in_motion_neg, jogging_pos, jogging_neg, connected, homing, homed, position_error,
                                   error, enabled)
                    self.moving[axis] = in_motion_pos | in_motion_neg
                    self.homed[axis] = homed
                    self.current_position[axis] = self.parse_position(pos)

                    if self.logging_running:
                        if self.movement_log is not None:
                            tmp = ""
                            for a in self.axes:
                                tmp += f"{self.current_position[a]},"
                            self.write_to_disk(tmp)

                else:
                    self.log.info("KDC %s unknown message (%s)", source, hex(cmd))
                    self.flush_buffers()
            
    def getSoftwareLimits(self, axis=None):
        a = self.convertAxis(axis)
        return (self.cntsToMm(self.limit_array[a][3], axis=axis), self.cntsToMm(self.limit_array[a][2], axis=axis))
    
    def setLowerLimit(self, limit, axis=None):
        a = self.convertAxis(axis)
        self.limit_array[a][2] = kdc.mmToCnts(limit, axis=a)
        self.limit_array[a][4] = 0x02 # enable limits
        self.long_write_to_KDC101(LIMITS_SET, a, "HHHiiH", [self.channel, *self.limit_array[a]], 16)

    def setUpperLimit(self, limit, axis=None):
        a = self.convertAxis(axis)
        self.limit_array[a][3] = kdc.mmToCnts(limit, axis=a)
        self.limit_array[a][4] = 0x02 # enable limits
        self.long_write_to_KDC101(LIMITS_SET, a, "HHHiiH", [self.channel, *self.limit_array[a]], 16)

    def getPosition(self, axis=None, notify=True):
        """Return the position of the specified encoder."""
        a = self.convertAxis(axis)
        return float(self.current_position[a])

    def motorOn(self, axis=None):
        """Turn on the specified axis."""
        a = self.convertAxis(axis)
        self.write_to_KDC101(MODULE_ENABLE_SET, self.channel, 0x01, a)

    def motorOff(self, axis=None):
        """Turn off the specified axis."""
        a = self.convertAxis(axis)
        self.write_to_KDC101(MODULE_ENABLE_SET, self.channel, 0x02, a)

    # MTS25-Z8 Maximum Acceleration 4.5 mm/s2
    # Z906 Maximum Acceleration 4.0 mm/s2

    def getAcceleration(self, axis=None):
        """Return the acceleration of the specified axis (mm/sec^2)."""
        a = self.convertAxis(axis)
        return self.acceleration[a]

    def setAcceleration(self, acceleration, axis=None):
        """Set the acceleration for the specified axis (mm/sec^2)."""
        a = self.convertAxis(axis)
        self.acceleration[a] = acceleration
        vel = self.velToCnts(self.speed[a], axis=a)
        acc = self.accToCnts(acceleration, axis=a)
        self.long_write_to_KDC101(VEL_ACC_SET, a, "Hiii", [self.channel, 0, acc, vel], 14)

    # MTS25-Z8 Maximum Velocity 2.4 mm/s
    # Z906 Maximum Velocity 2.6 mm/s

    def getSpeed(self, axis=None):
        """Return the speed for the specified axis (mm/sec)."""
        a = self.convertAxis(axis)
        return self.speed[a]

    def setSpeed(self, speed, axis=None):
        """Set the speed for the specified axis (mm/sec)."""
        a = self.convertAxis(axis)
        self.speed[a] = speed
        vel = self.velToCnts(speed, axis=a)
        acc = self.accToCnts(self.acceleration[a], axis=a)
        self.long_write_to_KDC101(VEL_ACC_SET, a, "Hiii", [self.channel, 0, acc, vel], 14)

    def home(self):
        for axis in self.axes:
            a = self.convertAxis(axis)
            if not self.homed[a]:
                self.write_to_KDC101(HOME_CMD, self.channel, 0x00, a)
                self.log.info("Start homing...")

        for axis in self.axes:
            a = self.convertAxis(axis)
            if not self.homed[a]:
                start = time.time()
                while (self.homed[a] != True) and (time.time()-start < 60): # 60 second timeout
                    time.sleep(0.1)

                if self.homed[a] != True:
                    self.log.error("Homing Failed!")
                    return

        self.log.info("Homing complete.")

        for axis in self.axes:
            a = self.convertAxis(axis)
            self.setSpeed(self.getDefaultSpeed(a), axis=a)
            self.setAcceleration(self.getDefaultAcceleration(a), axis=a)

        

    # pylint: disable=too-many-arguments
    def relMove(self, mm, speed=None, acceleration=None, wait_for_settling=True, axis=None):
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

        start_position = self.getPosition(axis=a)
        self.log.info("Move axis %s to relative position %s", a, mm)
        self.long_write_to_KDC101(MOV_REL_CMD, a, "Hi", [self.channel, self.mmToCnts(mm, axis=a)], 6)
        self.moving[a] = True
        finished_succeccfully = self.confirmMoveFinished(axis=a)
        if not finished_succeccfully:
            self.log.warning("Move failed. Going to position 0 and retrying")
            self.absMove(0.0, speed=speed, acceleration=acceleration, axis=axis)
            self.absMove(start_position + mm, speed=speed, acceleration=acceleration, axis=axis)

        if speed is not None:
            self.setSpeed(old_speed, axis=a)
        if acceleration is not None:
            self.setAcceleration(old_acceleration, axis=a)
        return self.getPosition(axis=a)

    # pylint: disable=too-many-arguments
    def absMove(
        self,
        mm,
        speed=None,
        acceleration=None,
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

        self.log.info("Move axis %s to absolute position %s", a, mm)
        self.long_write_to_KDC101(MOV_ABS_CMD, a, "Hi", [self.channel,self.mmToCnts(mm, axis=a)], 6)
        self.moving[a] = True
        finished_succeccfully = self.confirmMoveFinished(axis=a)
        if not finished_succeccfully:
            self.log.warning("Move failed. Going to position 0 and retrying")
            self.absMove(0.0, speed=speed, acceleration=acceleration, axis=axis)
            self.absMove(mm, speed=speed, acceleration=acceleration, axis=axis)

        if speed is not None:
            self.setSpeed(old_speed, axis=a)
        if acceleration is not None:
            self.setAcceleration(old_acceleration, axis=a)
        return self.getPosition(axis=a)
    
    def confirmMoveFinished(self, timeout=30, axis=None):
        start = time.time()
        while (self.moving[axis] == True) and (time.time()-start < timeout):
            time.sleep(0.1)

        if self.moving[axis] == True:
            self.log.error("Move Failed!")
            return False

        self.log.debug("Move Complete")
        return True

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

        self.setSpeed(abs(speed))
        self.setAcceleration(acceleration)
        self.log.info("Start jog on axis %s at speed %s mm/sec", a, speed)
        self.write_to_KDC101(MOV_VEL_CMD, self.channel, 0x01 if speed < 0 else 0x02, a)

    def stopJog(self, axis=None):
        """Stop a jog, non-blocking."""
        a = self.convertAxis(axis)
        self.log.info("Stop jog on axis %s", a)
        self.write_to_KDC101(MOV_STOP_CMD, self.channel, 0x01, a)
        self.jogging[a] = False
        self.setSpeed(self.pre_jog_speed[a])
        self.setAcceleration(self.pre_jog_acceleration[a])

    def setup_log_file(self, filename):
        """Set the log file."""
        if self.movement_log is None and filename is not None:
            self.movement_log = str(Path(filename) / "kdc_movement_data.csv")
            async_file_hander.write(self.movement_log, "timestamp,")
            for a in self.axes_common_names:
                async_file_hander.write(self.movement_log, f"{a} position_mm,")
            async_file_hander.write(self.movement_log, "\n")
        elif self.movement_log is not None and filename is None:
            self.movement_log = None

    def logging_start(self):
        """
        Starts collecting position data
        """
        if not self.logging_running:
            self.logging_running = True
            self.log.info("KDC logging started")

    def logging_stop(self):
        """
        Stops collecting position data
        """
        if self.logging_running:
            self.logging_running = False
            self.log.info("KDC logging stopped")

################################# Parent class functions #######################################

    def getDefaultFocusSpeed(self):
        return self.getDefaultSpeed("Focus")

    def getDefaultFocusAcceleration(self):
        return self.getDefaultAcceleration("Focus")

    def getFocusPosition(self, notify=True):
        return self.getPosition(axis="Focus")

    def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.absMove(mm, speed=speed, acceleration=acceleration, axis="Focus")

    def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.relMove(mm, speed=speed, acceleration=acceleration, axis="Focus")

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
            ll = 0.0
        if self.limits[a][1] is not None:  
            ul = sl[1]
        else:
            ul = self.max_travel_mm[a]
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

if __name__ == "__main__":
    kdc = KDC101(config_dict={
        "dummy": False,
        "vendor_id": 1027,
        "product_id": 64240,
        "baudrate": 115200,
        "default_axis": "0x50",
        "axes": [
            "0x50"
        ],
        "axes_common_names": [
            "Focus"
        ],
        "axes_travel": {
            "0x50": 25.0
        },
        "axes_ctspmm": {
            "0x50": 34554.96 
        },
        "axes_speed": {
            "0x50": 2.777
        },
        "axes_acceleration": {
            "0x50": 1.486
        },
        "limits": {
            "0x50": [None,None]
        },
        "moving_shifts_image": True
    })

    kdc.connect()
    kdc.initialize()
    kdc.home()

    # print("\nBay info")
    # kdc.write_to_KDC101(HUB_BAYUSED_GET, 0x00, 0x00, "0x50")
    
    for axis in kdc.axes:
        print(f"\n{axis}")
        a = kdc.convertAxis(axis)
        # print("\tIdent")
        # kdc.write_to_KDC101(MODULE_IDENT_CMD, kdc.channel, 0x00, a)
        kdc.absMove(1, axis=a)
        kdc.relMove(-0.5, axis=a)

        kdc.startJog(speed=kdc.getDefaultSpeed(axis=a), acceleration=kdc.getDefaultAcceleration(axis=a), axis=a)
        time.sleep(1)
        kdc.stopJog(axis=a)
        # print("\tParam dump")
        # kdc.write_to_KDC101(0x0414, kdc.channel, 0x00, a)
        # time.sleep(0.5)
        # kdc.write_to_KDC101(0x0417, kdc.channel, 0x00, a)
        # time.sleep(0.5)
        # kdc.write_to_KDC101(0x043B, kdc.channel, 0x00, a)
        # time.sleep(0.5)
        # kdc.write_to_KDC101(0x0441, kdc.channel, 0x00, a)
        # time.sleep(0.5)
        # kdc.write_to_KDC101(0x0424, kdc.channel, 0x00, a)
        # time.sleep(0.5)
        # print("\tSet new limits")
        # kdc.limit_array[a][3] = kdc.mmToCnts(0, axis=a)
        # kdc.limit_array[a][2] = kdc.mmToCnts(25, axis=a)
        # kdc.limit_array[a][4] = 0x02 # enable limit
        # kdc.long_write_to_KDC101(LIMITS_SET, a, "HHHiiH", [kdc.channel, *kdc.limit_array[a]], 16)
        # time.sleep(0.25)
        # kdc.long_write_to_KDC101(0x04B9, a, "HH", [kdc.channel, LIMITS_SET], 4)

    time.sleep(1)
    kdc.disconnect()