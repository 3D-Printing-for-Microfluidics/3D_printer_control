from functools import wraps


def dummy_log(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        print(f.__qualname__, {**dict(zip(f.__code__.co_varnames, args)), **kwargs})
        result = f(*args, **kwargs)
        print(f.__qualname__, "return:", result)
        return result

    return wrapper


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
