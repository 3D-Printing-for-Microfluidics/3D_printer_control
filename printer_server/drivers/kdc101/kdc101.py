import time
import logging
from struct import pack, unpack
from printer_server.drivers.generic_drivers import USBSerial, FocusStageDriver

class KDC101(USBSerial, FocusStageDriver):
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__("KDC", vid=config_dict["vendor_id"], pid=config_dict["product_id"], baudrate=config_dict["baudrate"], timeout=0.1, logger=self.log)

        self.homed = False
        self.Device_Unit_SF = 34304.0  # pg 34 of protocol PDF (as of Issue 23)
        self.Channel = 1
        self.destination = 0x50
        self.source = 0x01
        self.maxPos = 25.0
        self.minPos = 0.0
        self.relativeMode = True
        self.config_dict = config_dict
        self.initialized = None

    def connect(self, shutdown):
        super().connect(shutdown)
        if self.connected is None:
            self.getHardwareInfo()
            self.enableStage(enable=True)


    def disconnect(self):
        if self.connected is not None and self.connected is not False:
            try:
                self.enableStage(enable=False)
            except:
                pass
        super().disconnect()


    ############################# Parent class functions #####################################

    def setup_log_file(self, filename):
        pass

    def logging_start(self):
        pass

    def logging_stop(self):
        pass

    def initialize(self):
        pass

    def getFocusPosition(self, notify=True):
        return self.getCurrentPos()/1000

    def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.move(mm, microns=False, relative=False)

    def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.move(mm, microns=False, relative=True)

    def startFocusJog(self, speed=None, acceleration=None):
        self.log.warn("KDC Jogging not implemented")

    def stopFocusJog(self):
        self.log.warn("KDC Jogging not implemented")

    ##############################################################################################
            
    def home(self):
        # Home Stage; MGMSG_MOT_MOVE_HOME
        self.write_bytes(
            pack("<HBBBB", 0x0443, self.Channel, 0x00, self.destination, self.source)
        )
        self.log.info("Homing KDC...")

        # Confirm stage homed before advancing; MGMSG_MOT_MOVE_HOMED
        Rx = ""
        Homed = pack("<H", 0x0444)
        # we do this with number of attempts as it might otherwise freeze here
        # (300 attempts = ~25 sec) if it freezes, we just home again
        attempts = 0
        while Rx != Homed and not self.homed:
            if attempts > 30:
                # self.log.info("Homing Failed: Trying again")
                self.write_bytes(
                    pack(
                        "<HBBBB",
                        0x0443,
                        self.Channel,
                        0x00,
                        self.destination,
                        self.source,
                    )
                )
                attempts = 0
            Rx = self.read_bytes(2)
            attempts = attempts + 1

        self.homed = True
        self.log.info("Homed KDC")
        self.flush_buffers()

    def move(self, pos, microns=True, relative=True):

        prev_pos = self.getFocusPosition()

        # update positioning mode
        if relative:
            self.setRelative()
        else:
            self.setAbsolute()

        if microns:
            position = pos * 1e-3  # translate into um
        else:
            position = pos

        if self.relativeMode:
            # Move to absolute position in mm; MGMSG_MOT_MOVE_ABSOLUTE (long version)
            # currPos = self.getCurrentPos()
            dUnitpos = int(self.Device_Unit_SF * position)
            code = 0x0448

            # if currPos returns as 'undef' we don't know the position of the stage.
            # So the movement may work or it might not.
            # Best practice is to home after every initialization.
            # Matthew - 10/4/19 - this doesn't appear to have been tested well, removing it for now
            # if not isinstance(currPos, str):
            #     if self.minPos > currPos + position <= self.maxPos:
            #         self.log.debug("It's false: currPos: {} pos: {}".format(currPos, position))
            #         return False
        elif abs(position) < 25:
            dUnitpos = int(self.Device_Unit_SF * abs(position))
            code = 0x0453
        else:
            return False

        # we do this recursively otherwise it might freeze here (each ittr = ~10 sec)
        # if it freezes, we just home again
        self.log.info("Moving stage to %s", pos)
        self.write_bytes(
            pack(
                "<HBBBBHi",
                code,
                0x06,
                0x00,
                self.destination | 0x80,
                self.source,
                self.Channel,
                dUnitpos,
            )
        )
        finished_succeccfully = self.confirmMoveFinished()
        if not finished_succeccfully:
            self.log.warning("Move failed. Going to position 0 and retrying")
            self.move(0.0, relative=False)
            if relative:
                self.move(prev_pos + position, microns = False, relative=False)
            else:
                self.move(position, microns = False, relative=False)
        return True

    def setRelative(self):
        self.relativeMode = True

    def setAbsolute(self):
        self.relativeMode = False

    def confirmMoveFinished(self):
        # Confirm stage completed move before advancing; MGMSG_MOT_MOVE_COMPLETED
        Rx = ""
        Moved = pack("<H", 0x0464)
        attempts = 0
        while Rx != Moved:
            if attempts > 100:
                self.log.info("Move Failed: Trying again")
                return False
            Rx = self.read_bytes(2)
            attempts = attempts + 1

        self.log.debug("Move Complete")
        self.flush_buffers()
        return True

    def sendServerAlive(self):
        self.write_bytes(
            pack("<HBBBB", 0x0492, 0x00, 0x00, self.destination, self.source)
        )

    def getHardwareInfo(self):
        # Get HW info; MGMSG_HW_REQ_INFO; may be require by a K Cube to
        #  allow confirmation Rx messages
        self.write_bytes(pack("<HBBBB", 0x0005, 0x00, 0x00, 0x50, 0x01))
        self.flush_buffers()

    def enableStage(self, enable=True):
        # Enable Stage; MGMSG_MOD_SET_CHANENABLESTATE
        state = 0x01 if enable else 0x02
        self.write_bytes(
            pack("<HBBBB", 0x0210, self.Channel, state, self.destination, self.source)
        )
        time.sleep(0.1)

    def getCurrentPos(self):
        # for some reason sometimes the first one fails.
        # if it is startup, the first 2 fail
        # so we get it twice
        self.getCurrentPosHelper()
        self.getCurrentPosHelper()
        return self.getCurrentPosHelper()

    def getCurrentPosHelper(self):
        # Request Position; MGMSG_MOT_REQ_POSCOUNTER
        self.write_bytes(
            pack("<HBBBB", 0x0411, self.Channel, 0x00, self.destination, self.source)
        )

        # Read back position returns by the cube; Rx message MGMSG_MOT_GET_POSCOUNTER
        _, _, position_dUnits = unpack(
            "<6sHI", self.read_bytes(12)
        )  # first two returns are header and chan_dent
        getpos = position_dUnits / float(self.Device_Unit_SF)

        if int(getpos) == 33400:
            return "undef"

        if int(getpos) == 125203:
            getpos = 0.0

        getpos = round(
            getpos * 1000, 1
        )  # convert to microns and round to 1 decimal place
        self.flush_buffers()  # added to test if it fixes the read error

        if not self.homed and getpos == 0.0:
            return "undef"

        return getpos


if __name__ == "__main__":
    kc = KDC101()
    kc.home()
    for _ in range(2):
        kc.move(1000)
        kc.move(-1000)
    kc.move(10000)
