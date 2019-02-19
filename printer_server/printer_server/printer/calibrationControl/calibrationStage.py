import abc

class CalibrationStage(metaclass=abc.ABCMeta):
    
    @abc.abstractmethod
    def move(self):
        raise NotImplementedError

    @abc.abstractmethod
    def initialize(self):
        raise NotImplementedError

    @abc.abstractmethod
    def home(self):
        raise NotImplementedError

    @abc.abstractmethod
    def getCurrentPos(self):
        raise NotImplementedError

    @abc.abstractmethod
    def setRelative(self):
        raise NotImplementedError

    @abc.abstractmethod
    def setAbsolute(self):
        raise NotImplementedError