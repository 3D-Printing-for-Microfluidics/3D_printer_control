from printer_server.logging_handler import dummy_log


class KDC101_dummy:
    @dummy_log
    def __init__(self, *args, **kwargs):
        self.position = 0

    @dummy_log
    def home(self):
        pass

    @dummy_log
    def move(self, *args, **kwargs):
        if "relative" in kwargs and kwargs["relative"]:
            self.position += args[0]
        else:
            self.position = args[0]

    @dummy_log
    def setRelative(self, *args, **kwargs):
        pass

    @dummy_log
    def setAbsolute(self, *args, **kwargs):
        pass

    @dummy_log
    def confirmMoveFinished(self, *args, **kwargs):
        pass

    @dummy_log
    def initialize(self, *args, **kwargs):
        pass

    @dummy_log
    def sendServerAlive(self, *args, **kwargs):
        pass

    @dummy_log
    def getHardwareInfo(self, *args, **kwargs):
        pass

    @dummy_log
    def enableStage(self, *args, **kwargs):
        pass

    @dummy_log
    def getUSBDevice(self, *args, **kwargs):
        pass

    @dummy_log
    def flushUSB(self, *args, **kwargs):
        pass

    @dummy_log
    def getCurrentPos(self, *args, **kwargs):
        return self.position
