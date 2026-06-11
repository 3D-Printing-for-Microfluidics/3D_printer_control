# Based on https://www.thorlabs.com/Software/Motion%20Control/APT_Communications_Protocol.pdf

import time
import atexit
import logging
import threading
from pathlib import Path
from datetime import datetime
from struct import pack, unpack
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.drivers.generic_drivers import USBSerial

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
DC_UPDATE_GET = 0x0490
DC_UPDATE_ACK = 0x0492

BOW_INDEX_GET = 0x04F5
HOME_PARAMS_SET = 0x0440
HOME_PARAMS_GET = 0x0441

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
    "DC_UPDATE_RSP": 0x0491,
    "UPDATE_RSP": 0x0481,
    "BOW_INDEX_RSP": 0x04F6,
    "HOME_PARAMS_RSP": 0x0442,
}


class ThorlabsAPT(USBSerial):
    def __init__(
        self,
        config_dict=None,
        log_level=logging.DEBUG,
        driver_name="ThorlabsAPT",
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.movement_log = None
        self.config_dict = config_dict
        self.driver_name = driver_name

        self.default_axis = config_dict["default_axis"]
        self.axes = config_dict["axes"]
        self.axes_common_names = config_dict["axes_common_names"]
        self.max_travel_mm = config_dict["axes_travel"]
        self.ctspmm = config_dict["axes_ctspmm"]
        self.ctspmms = config_dict["axes_ctspmms"]
        self.ctspmmss = config_dict["axes_ctspmmss"]
        self.default_speed = config_dict["axes_speed"]
        self.default_acceleration = config_dict["axes_acceleration"]
        self.mirroring = config_dict["mirroring"]
        self.limits = config_dict["limits"]
        self.homing_timeout = config_dict.get("axes_homing_timeout", 60.0)
        self.move_timeout = config_dict.get("axes_timeout", 60.0)

        self.controllers = {}
        self.threads = {}
        self.thread_runnings = {}
        for a in self.axes:
            self.controllers[a] = USBSerial(
                f"ThorlabsAPT_{self.getCommonName(a)}",
                vid=config_dict["vendor_ids"][a],
                pid=config_dict["product_ids"][a],
                sn=config_dict["serial_numbers"][a],
                baudrate=config_dict["baudrates"][a],
                timeout=0.25,
                logger=self.log,
            )

            self.threads[a] = Thread(
                self.log,
                name=f"{self.driver_name}_{a}_loop_thread",
                target=self.loop,
                kwargs={"axis": a},
            )
            self.threads[a].daemon = True
            self.thread_runnings[a] = False

        self.logging_running = False

        self.channel = 1
        self.source = 0x01
        self.dest = 0x50

        self.axes_homed = {}
        self.moving = {}
        self.moving_dir = {}
        self.jogging = {}
        self.speed = {}
        self.acceleration = {}
        self.pre_jog_speed = {}
        self.pre_jog_acceleration = {}
        self.current_position = {}
        self.limit_array = {}
        self.homing_array = {}
        for a in self.axes:
            self.axes_homed[a] = False
            self.moving[a] = False
            self.moving_dir[a] = None
            self.jogging[a] = False
            self.speed[a] = 0
            self.acceleration[a] = 0
            self.pre_jog_speed[a] = 0
            self.pre_jog_acceleration[a] = 0
            self.current_position[a] = 0
            self.limit_array[a] = []
            self.homing_array[a] = []

        self.connected = None
        self.initialized = None
        self.homed = None

    def getCommonName(self, axis):
        if axis is None:
            axis = self.default_axis
        elif type(axis) is int:
            axis = str(hex(axis))
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
        if self.initialized is None:
            self.initialized = False
            for a in self.axes:
                self.thread_runnings[a] = True
                self.threads[a].start()

            for axis in self.axes:
                a = self.convertAxis(axis)
                self.getHardwareInfo(axis=a)
                time.sleep(0.25)
                self.motorOn(axis=a)
                time.sleep(0.25)
                self.write_to_APT(a, VEL_ACC_GET, self.channel, 0x00)
                time.sleep(0.25)
                self.write_to_APT(a, LIMITS_GET, self.channel, 0x00)
                time.sleep(0.25)
                self.write_to_APT(a, HOME_PARAMS_GET, self.channel, 0x00)
                time.sleep(0.25)
                self.homing_array[a][2] = self.velToCnts(
                    self.config_dict["axes_homing_speed"][a], axis=a
                )
                self.long_write_to_APT(
                    a, HOME_PARAMS_SET, "HHHii", [self.channel, *self.homing_array[a]], 14
                )
                # self.write_to_APT(a, BOW_INDEX_GET, self.channel, 0x00)
                # time.sleep(0.25)
                # self.write_to_APT(a, DC_UPDATE_GET, self.channel, 0x00)
                self.write_to_APT(a, HW_START_STATUS_CMD, 0x00, 0x00)
                time.sleep(0.25)
            self.initialized = True
        else:
            while self.initialized is False:
                time.sleep(0.1)

    def connect(self):
        if self.connected is None:
            self.connected = False
            threads = []
            for a in self.axes:
                cntlr = self.controllers[a]
                thread = Thread(
                    self.log, name=f"apt_{a}_connect_thread", target=cntlr.connect
                )
                thread.start()
                threads.append(thread)
            for t in threads:
                t.join()
            for a, cntlr in self.controllers.items():
                if cntlr.connected is None or not cntlr.connected:
                    self.log.error(
                        "%s - Failed to connect to %s (%s)",
                        self.driver_name,
                        a,
                        cntlr.readable_name,
                    )
                    return False
            self.connected = True
            return True
        else:
            while self.connected is False:
                time.sleep(0.1)
            return True

    def disconnect(self):
        if self.connected is not None and self.connected is not False:
            for axis in self.axes:
                a = self.convertAxis(axis)
                try:
                    self.thread_runnings[a] = False
                    self.threads[a].join()
                    self.threads[a] = Thread(
                        self.log,
                        name=f"{self.driver_name}_{a}_loop_thread",
                        target=self.loop,
                        kwargs={"axis": a},
                    )
                    self.threads[a].daemon = True

                    self.motorOff(axis=a)
                    self.write_to_APT(a, HW_STOP_STATUS_CMD, 0x00, 0x00)
                    self.write_to_APT(a, HW_DISCONNECT_CMD, 0x00, 0x00)
                    cntlr = self.controllers[a]
                    cntlr.disconnect()
                except:
                    pass

    def getHardwareInfo(self, axis=None):
        # Get HW info; MGMSG_HW_REQ_INFO; may be require by a K Cube to
        #  allow confirmation Rx messages
        a = self.convertAxis(axis)
        self.write_to_APT(a, HW_INFO_GET, 0x00, 0x00)

    # def sendServerAlive(self, axis=None):
    #     a = self.convertAxis(axis)
    #     self.write_to_APT(a, DC_UPDATE_ACK, 0x00, 0x00)

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
        return int(vel * (self.ctspmms[a]))

    def cntsToVel(self, counts, axis=None):
        a = self.convertAxis(axis)
        return counts / (self.ctspmms[a])

    def accToCnts(self, acc, axis=None):
        a = self.convertAxis(axis)
        return int(acc * (self.ctspmmss[a]))

    def cntsToAcc(self, counts, axis=None):
        a = self.convertAxis(axis)
        return counts / (self.ctspmmss[a])

    def write_to_APT(self, axis, cmd, _a, _b):
        msg = pack(f"<H4B", cmd, _a, _b, self.dest, 0x01)
        # self.log.debug("%s - Sent : '%s', a:%s, b:%s, dest:%s, source:%s", self.driver_name, cmd, _a, _b, self.dest, 0x01)
        # self.log.debug("%s - Sent : '%s'", self.driver_name, msg)
        cntlr = self.controllers[axis]
        cntlr.write_bytes(msg)

    def long_write_to_APT(self, axis, cmd, extra_format, extra_data, extra_len):
        msg = pack(
            f"<2H2B{extra_format}",
            cmd,
            extra_len,
            self.dest | 0x80,
            0x01,
            *extra_data,
        )
        # self.log.debug("%s - Sent : '%s'", self.driver_name, msg)
        cntlr = self.controllers[axis]
        cntlr.write_bytes(msg)

    def parse_position(self, pos, axis=None):
        a = self.convertAxis(axis)
        getpos = self.cntsToMm(pos, axis=a)

        if not self.axes_homed[a]:
            pos = "undef"

        if int(getpos) == 33400:
            pos = "undef"
        elif int(getpos) == 125203:
            pos = 0.0
        else:
            pos = round(getpos, 4)

        return pos

    def loop(self, axis=None):
        ax = self.convertAxis(axis)
        cntlr = self.controllers[ax]
        while self.thread_runnings[ax]:
            if cntlr.in_waiting >= 6:
                rsp = cntlr.read_bytes(6)
                cmd, a, b, dest, source = unpack("<H4B", rsp)
                has_extra_bytes = (dest & 0x80) > 0
                if has_extra_bytes:
                    count = unpack("<H", pack("<BB", a, b))[0]
                    extra_bytes = cntlr.read_bytes(count)
                dest &= 0x7F

                # self.log.debug("%s - Recieved : '%s', a:%s, b:%s, dest:%s, source:%s", self.driver_name, cmd, a, b, dest, source)
                # if has_extra_bytes:
                #     self.log.debug("%s - Recieved : '%s'", self.driver_name, extra_bytes)

                # axis = self.convertAxis(source)

                if cmd == RSPS["HW_ERROR_RSP"]:
                    ident, code, error, _ = unpack("<HH63sB", extra_bytes)
                    self.log.warning(
                        "%s - %s - %s error %s (%s)",
                        self.driver_name,
                        ax,
                        source,
                        code,
                        error.rstrip().decode("utf-8"),
                    )

                elif cmd == RSPS["HW_INFO_RSP"]:
                    serial, model, type, firm_ver, _, hw_ver, mod_ver, nchs = unpack(
                        "<i8sH4s60s3H", extra_bytes
                    )
                    self.log.debug(
                        "%s - %s - %s hardware info: serial %s, model %s, type %s, fw ver %s, hw ver %s, mod %s, nchs %s",
                        self.driver_name,
                        ax,
                        source,
                        serial,
                        model,
                        type,
                        firm_ver,
                        hw_ver,
                        mod_ver,
                        nchs,
                    )

                elif cmd == RSPS["HUB_BAYUSED_RSP"]:
                    if a == -0x01:  # standalone
                        bay = None
                    elif a == 0x00:  # unknown
                        bay = -1
                    else:  # in bay x
                        bay = a
                    self.log.debug(
                        "%s - %s - %s in bay %s (%s)",
                        self.driver_name,
                        ax,
                        source,
                        a,
                        bay,
                    )

                elif cmd == RSPS["POS_RSP"]:
                    channel, pos = unpack("<Hi", extra_bytes)
                    self.current_position[ax] = self.parse_position(pos)
                    self.log.debug(
                        "%s - %s - %s at %s",
                        self.driver_name,
                        ax,
                        source,
                        self.current_position[ax],
                    )

                elif cmd == RSPS["VEL_ACC_RSP"]:
                    channel, _, acc, speed = unpack("<Hiii", extra_bytes)
                    self.speed[ax] = self.cntsToVel(speed, axis=ax)
                    self.acceleration[ax] = self.cntsToAcc(acc, axis=ax)
                    self.log.debug(
                        "%s - %s - %s speed:%s acc:%s",
                        self.driver_name,
                        ax,
                        source,
                        self.speed[ax],
                        self.acceleration[ax],
                    )

                elif cmd == RSPS["LIMITS_RSP"]:
                    channel, upper_mode, lower_mode, upper_soft, lower_soft, soft_mode = (
                        unpack("<HHHiiH", extra_bytes)
                    )
                    self.limit_array[ax] = [
                        upper_mode,
                        lower_mode,
                        upper_soft,
                        lower_soft,
                        soft_mode,
                    ]
                    self.log.debug(
                        "%s - %s - %s limit: upper hard %s lower hard %s, upper soft %s, lower soft %s, soft mode %s",
                        self.driver_name,
                        ax,
                        source,
                        upper_mode,
                        lower_mode,
                        self.cntsToMm(upper_soft, axis=ax),
                        self.cntsToMm(lower_soft, axis=ax),
                        soft_mode,
                    )

                elif cmd == RSPS["HOME_PARAMS_RSP"]:
                    channel, direction, limit_switch, velocity, offset = unpack(
                        "<HHHii", extra_bytes
                    )
                    self.homing_array[ax] = [direction, limit_switch, velocity, offset]
                    self.log.debug(
                        "%s - %s - %s channel:%s, direction:%s, limit_switch:%s, velocity:%s, offset:%s",
                        self.driver_name,
                        ax,
                        source,
                        channel,
                        direction,
                        limit_switch,
                        velocity,
                        offset,
                    )

                elif cmd == RSPS["BOW_INDEX_RSP"]:
                    channel, bow_index = unpack("<HH", extra_bytes)
                    self.log.debug(
                        "%s - %s - %s channel:%s, bow_index:%s",
                        self.driver_name,
                        ax,
                        source,
                        channel,
                        bow_index,
                    )

                elif cmd == RSPS["HOME_RSP"]:
                    # channel = a
                    self.axes_homed[ax] = True
                    self.log.debug("%s - %s - %s homed", self.driver_name, ax, source)

                elif (
                    cmd == RSPS["MOV_RSP"]
                    or cmd == RSPS["MOV_STOP_RSP"]
                    or cmd == RSPS["DC_UPDATE_RSP"]
                    or cmd == RSPS["UPDATE_RSP"]
                ):
                    if len(extra_bytes) == 14:
                        channel, pos, speed, current, status = unpack(
                            "<HiHHI", extra_bytes
                        )
                    elif len(extra_bytes) == 28:
                        channel, pos, enc, status, channel2 = unpack(
                            "<HiiIH", extra_bytes
                        )
                    else:
                        self.log.warning(
                            "%s - %s - %s unknown MOV_RSP length %s",
                            self.driver_name,
                            ax,
                            source,
                            len(extra_bytes),
                        )
                        continue
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
                    # self.sendServerAlive(c, axis=ax)
                    if len(extra_bytes) == 14:
                        self.log.debug(
                            "%s - %s - %s update: pos %s, speed %s, upper_hard_limit %s, lower_hard_limit %s, upper_soft_limit %s, \
                                    lower_soft_limit %s, in_motion_pos %s, in_motion_neg %s, jogging_pos %s, jogging_neg %s, connected %s, \
                                    homing %s, homed %s, pos_error %s, error %s, enabled %s",
                            self.driver_name,
                            ax,
                            source,
                            self.parse_position(pos),
                            self.cntsToVel(speed, axis=ax),
                            upper_hard_limit,
                            lower_hard_limit,
                            upper_soft_limit,
                            lower_soft_limit,
                            in_motion_pos,
                            in_motion_neg,
                            jogging_pos,
                            jogging_neg,
                            connected,
                            homing,
                            homed,
                            position_error,
                            error,
                            enabled,
                        )
                    elif len(extra_bytes) == 28:
                        self.log.debug(
                            "%s - %s - %s update: pos %s, enc %s, upper_hard_limit %s, lower_hard_limit %s, upper_soft_limit %s, \
                                    lower_soft_limit %s, in_motion_pos %s, in_motion_neg %s, jogging_pos %s, jogging_neg %s, connected %s, \
                                    homing %s, homed %s, pos_error %s, error %s, enabled %s",
                            self.driver_name,
                            ax,
                            source,
                            self.parse_position(pos),
                            self.parse_position(enc),
                            upper_hard_limit,
                            lower_hard_limit,
                            upper_soft_limit,
                            lower_soft_limit,
                            in_motion_pos,
                            in_motion_neg,
                            jogging_pos,
                            jogging_neg,
                            connected,
                            homing,
                            homed,
                            position_error,
                            error,
                            enabled,
                        )

                    self.moving[ax] = in_motion_pos | in_motion_neg
                    self.axes_homed[ax] = homed
                    self.current_position[ax] = self.parse_position(pos)

                    if self.logging_running:
                        if self.movement_log is not None:
                            tmp = ""
                            for _ax in self.axes:
                                tmp += f"{self.current_position[_ax]},"
                            self.write_to_disk(tmp)

                else:
                    self.log.debug(
                        "%s - %s - %s unknown message (%s)",
                        self.driver_name,
                        ax,
                        source,
                        hex(cmd),
                    )
                    cntlr.flush_buffers()

                # if limits are enabled, but the stage does not support it, use a python software limit
                if (
                    (self.limits[ax][0] is not None or self.limits[ax][1] is not None)
                    and len(self.limit_array[ax]) == 5
                    and self.limit_array[ax][4] == 0
                ):
                    pos = self.current_position[ax]
                    if self.axes_homed[ax] is True:
                        if (
                            self.moving_dir[ax] == "neg"
                        ):
                            if ((not self.mirroring[ax] and self.limits[ax][0] is not None and pos < self.limits[ax][0]) 
                                or (self.mirroring[ax] and self.limits[ax][1] is not None and pos < -self.limits[ax][1])):
                                self.log.info(f"{not self.mirroring[ax] and self.limits[ax][0] is not None and pos < self.limits[ax][0]}, {self.mirroring[ax] and self.limits[ax][1] is not None and pos < -self.limits[ax][1]}, {self.limits[ax]}")
                                self.log.warning(
                                    "%s - %s - %s position %s below lower limit %s" if not self.mirroring[ax] else "%s - %s - %s position %s above upper limit %s",
                                    self.driver_name,
                                    ax,
                                    source,
                                    pos if not self.mirroring[ax] else -pos,
                                    self.limits[ax][0] if not self.mirroring[ax] else -self.limits[ax][1],
                                )
                                self.fullstop(axis=ax)
                        elif (
                            self.moving_dir[ax] == "pos"
                        ):
                            if ((not self.mirroring[ax] and self.limits[ax][1] is not None and pos > self.limits[ax][1])
                                or (self.mirroring[ax] and self.limits[ax][0] is not None and pos > -self.limits[ax][0])):
                                self.log.info(f"{not self.mirroring[ax] and self.limits[ax][1] is not None and pos > self.limits[ax][1]}, {self.mirroring[ax] and self.limits[ax][0] is not None and pos > -self.limits[ax][0]}, {self.limits[ax]}")
                                self.log.warning(
                                    "%s - %s - %s position %s above upper limit %s" if not self.mirroring[ax] else "%s - %s - %s position %s below lower limit %s",
                                    self.driver_name,
                                    ax,
                                    source,
                                    pos if not self.mirroring[ax] else -pos,
                                    self.limits[ax][1] if not self.mirroring[ax] else -self.limits[ax][0],
                                )
                                self.fullstop(axis=ax)

    def getSoftwareLimits(self, axis=None):
        a = self.convertAxis(axis)
        if len(self.limit_array[a]) == 5:
            if self.limit_array[a][4] != 0:
                if self.mirroring[a]:
                    return (
                        self.cntsToMm(-self.limit_array[a][2], axis=axis),
                        self.cntsToMm(-self.limit_array[a][3], axis=axis),
                    )
                return (
                    self.cntsToMm(self.limit_array[a][3], axis=axis),
                    self.cntsToMm(self.limit_array[a][2], axis=axis),
                )
        return self.limits[a]

    def setLowerLimit(self, limit, axis=None):
        a = self.convertAxis(axis)
        if limit is None:
            limit = 0
        if self.mirroring[a]:
            self.limit_array[a][2] = self.mmToCnts(-limit, axis=a)
            self.limit_array[a][4] = 0x02  # enable limits
        else:
            self.limit_array[a][3] = self.mmToCnts(limit, axis=a)
            self.limit_array[a][4] = 0x02  # enable limits
        self.long_write_to_APT(
            a, LIMITS_SET, "HHHiiH", [self.channel, *self.limit_array[a]], 16
        )

    def setUpperLimit(self, limit, axis=None):
        a = self.convertAxis(axis)
        if limit is None:
            limit = self.max_travel_mm[a]
        if self.mirroring[a]:
            self.limit_array[a][3] = self.mmToCnts(-limit, axis=a)
            self.limit_array[a][4] = 0x02  # enable limits
        else:
            self.limit_array[a][2] = self.mmToCnts(limit, axis=a)
            self.limit_array[a][4] = 0x02  # enable limits
        self.long_write_to_APT(
            a, LIMITS_SET, "HHHiiH", [self.channel, *self.limit_array[a]], 16
        )

    def getLimits(self, axis=None):
        a = self.convertAxis(axis)
        sl = self.getSoftwareLimits(axis=a)
        if self.limits[a][0] is not None:
            ll = sl[0]
        else:
            ll = 0.0
        if self.limits[a][1] is not None:
            ul = sl[1]
        else:
            ul = self.max_travel_mm[a]
        return (ll, ul)

    def setLimits(self, limits=None, axis=None):
        a = self.convertAxis(axis)
        if limits is None:
            limits = self.limits[a]
        self.setLowerLimit(limits[0], axis=a)
        self.setUpperLimit(limits[1], axis=a)
        time.sleep(0.25)
        self.write_to_APT(a, LIMITS_GET, self.channel, 0x00)

    def getPosition(self, axis=None, notify=True):
        """Return the position of the specified encoder."""
        a = self.convertAxis(axis)
        if self.mirroring[a]:
            return float(-self.current_position[a])
        return float(self.current_position[a])

    def motorOn(self, axis=None):
        """Turn on the specified axis."""
        a = self.convertAxis(axis)
        self.write_to_APT(a, MODULE_ENABLE_SET, self.channel, 0x01)

    def motorOff(self, axis=None):
        """Turn off the specified axis."""
        a = self.convertAxis(axis)
        self.write_to_APT(a, MODULE_ENABLE_SET, self.channel, 0x02)

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
        self.long_write_to_APT(a, VEL_ACC_SET, "Hiii", [self.channel, 0, acc, vel], 14)

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
        self.long_write_to_APT(a, VEL_ACC_SET, "Hiii", [self.channel, 0, acc, vel], 14)

    def home(self):
        if self.homed is None:
            self.homed = False
            for axis in self.axes:
                a = self.convertAxis(axis)
                self.axes_homed[a] = False
                # if not self.axes_homed[a]:
                self.write_to_APT(a, HOME_CMD, self.channel, 0x00)
                self.log.info("%s start homing...", a)

            time.sleep(0.25)

            for axis in self.axes:
                a = self.convertAxis(axis)
                if not self.axes_homed[a]:
                    start = time.monotonic()
                    while (self.axes_homed[a] != True) and (
                        time.monotonic() - start < self.homing_timeout[a]
                    ):
                        time.sleep(0.1)

                    if self.axes_homed[a] != True:
                        self.log.error("%s homing failed!", a)
                        raise RuntimeError("%s homing failed!", a)

            self.log.info("%s homing complete.", self.driver_name)

            for axis in self.axes:
                a = self.convertAxis(axis)
                self.setSpeed(self.getDefaultSpeed(a), axis=a)
                self.setAcceleration(self.getDefaultAcceleration(a), axis=a)
            self.homed = True
        else:
            while self.homed is False:
                time.sleep(0.1)

    # pylint: disable=too-many-arguments
    def relMove(
        self, mm, speed=None, acceleration=None, wait_for_settling=True, axis=None
    ):
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
        if self.mirroring[a]:
            mm = -mm
        self.long_write_to_APT(
            a, MOV_REL_CMD, "Hi", [self.channel, self.mmToCnts(mm, axis=a)], 6
        )
        self.moving[a] = True
        self.moving_dir[a] = "pos" if mm > 0 else "neg" if mm < 0 else None
        time.sleep(0.25)
        finished_succeccfully = self.confirmMoveFinished(axis=a)

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
        if not self.axes_homed[a]:
            self.log.error("%s must home before using absolute movements!", a)
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
        if self.mirroring[a]:
            mm = -mm
        self.long_write_to_APT(
            a, MOV_ABS_CMD, "Hi", [self.channel, self.mmToCnts(mm, axis=a)], 6
        )
        self.moving[a] = True
        self.moving_dir[a] = (
            "pos"
            if mm - self.current_position[a] > 0
            else "neg" if mm - self.current_position[a] < 0 else None
        )
        time.sleep(0.25)
        finished_succeccfully = self.confirmMoveFinished(axis=a)

        if speed is not None:
            self.setSpeed(old_speed, axis=a)
        if acceleration is not None:
            self.setAcceleration(old_acceleration, axis=a)
        return self.getPosition(axis=a)

    def confirmMoveFinished(self, axis=None):
        a = self.convertAxis(axis)
        start = time.monotonic()
        while (self.moving[a] == True) and (time.monotonic() - start < self.move_timeout[a]):
            time.sleep(0.1)

        if self.moving[a] == True:
            self.log.error("%s move failed!", axis)
            return False

        self.log.debug("%s move complete", axis)
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

        if self.mirroring[a]:
            speed = -speed if speed is not None else None
        self.moving_dir[a] = "pos" if speed > 0 else "neg" if speed < 0 else None

        self.setSpeed(abs(speed))
        self.setAcceleration(acceleration)
        self.log.info("Start jog on axis %s at speed %s mm/sec", a, speed)
        self.write_to_APT(a, MOV_VEL_CMD, self.channel, 0x01 if speed < 0 else 0x02)

    def stopJog(self, axis=None):
        """Stop a jog, non-blocking."""
        a = self.convertAxis(axis)
        self.log.info("Stop jog on axis %s", a)
        self.write_to_APT(a, MOV_STOP_CMD, self.channel, 0x01)
        self.jogging[a] = False
        self.moving_dir[a] = None
        self.setSpeed(self.pre_jog_speed[a])
        self.setAcceleration(self.pre_jog_acceleration[a])

    def fullstop(self, axis=None):
        """Stop any motion, non-blocking."""
        a = self.convertAxis(axis)
        self.log.info("Stopping %s", a)
        self.write_to_APT(a, MOV_STOP_CMD, self.channel, 0x01)
        self.moving_dir[a] = None
        if self.jogging[a]:
            self.jogging[a] = False
            self.setSpeed(self.pre_jog_speed[a])
            self.setAcceleration(self.pre_jog_acceleration[a])
        else:
            self.moving[a] = False

    def setup_log_file(self, filename):
        """Set the log file."""
        if self.movement_log is None and filename is not None:
            self.movement_log = str(
                Path(filename) / f"{self.driver_name}_movement_data.csv"
            )
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
            self.log.info("%s logging started", self.driver_name)

    def logging_stop(self):
        """
        Stops collecting position data
        """
        if self.logging_running:
            self.logging_running = False
            self.log.info("%s logging stopped", self.driver_name)