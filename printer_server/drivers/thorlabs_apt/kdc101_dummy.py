
import time
import logging
from printer_server.logging_handler import dummy_log
from printer_server.drivers.generic_drivers import FocusStageDriver

class KDC101_dummy(FocusStageDriver):
    @dummy_log
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.homed = False
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.Device_Unit_SF = 34304.0
        self.Channel = 1
        self.destination = 0x50
        self.source = 0x01
        self.maxPos = 25.0
        self.minPos = 0.0
        self.relativeMode = True
        self.port = None
        self.serial_handle = None
        self.initialized = None
        self.config_dict = config_dict
        self.connected = None
        self.position = 0.0

    @dummy_log
    def find_device(self):
        return "dummy_port"

    @dummy_log
    def connect(self):
        if self.connected is None:
            self.connected = False
            self.port = self.find_device()
            self.serial_handle = "dummy_serial_handle"
            self.getHardwareInfo()
            self.enableStage(enable=True)
            self.connected = True
            return True
        else:
            while self.connected is False:
                time.sleep(0.1)

    @dummy_log
    def disconnect(self):
        if self.connected is not None and self.connected is not False:
            if self.serial_handle is not None:
                self.enableStage(enable=False)
                self.serial_handle = None

    # @dummy_log
    def setup_log_file(self, filename):
        pass

    # @dummy_log
    def logging_start(self):
        pass

    # @dummy_log
    def logging_stop(self):
        pass

    @dummy_log
    def initialize(self):
        pass

    def getDefaultFocusSpeed(self):
        return 0

    def getDefaultFocusAcceleration(self):
        return 0

    # @dummy_log
    def getFocusPosition(self, notify=True):
        return self.position/1000

    @dummy_log
    def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.move(mm, microns=False, relative=False)
        self.position = mm

    @dummy_log
    def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        self.move(mm, microns=False, relative=True)
        self.position += mm

    @dummy_log
    def startFocusJog(self, speed=None, acceleration=None):
        self.log.warning("KDC Jogging not implemented")

    @dummy_log
    def stopFocusJog(self):
        self.log.warning("KDC Jogging not implemented")

    @dummy_log
    def home(self):
        self.homed = True
        self.position = 0.0

    @dummy_log
    def move(self, pos, microns=True, relative=True):
        self.log.info("Moving stage to %s", pos)
        return True

    # @dummy_log
    def setRelative(self):
        self.relativeMode = True

    # @dummy_log
    def setAbsolute(self):
        self.relativeMode = False

    # @dummy_log
    def confirmMoveFinished(self):
        self.log.debug("Move Complete")
        return True

    # @dummy_log
    def sendServerAlive(self):
        pass

    # @dummy_log
    def getHardwareInfo(self):
        self.log.info("Getting hardware info...")

    # @dummy_log
    def enableStage(self, enable=True):
        state = "Enabled" if enable else "Disabled"
        self.log.info("Stage %s", state)

    # @dummy_log
    def flushUSB(self):
        pass

    # @dummy_log
    def getCurrentPos(self):
        return self.position

if __name__ == "__main__":
    kc = KDC101_dummy()
    kc.home()
    for _ in range(2):
        kc.move(1000)
        kc.move(-1000)
    kc.move(10000)