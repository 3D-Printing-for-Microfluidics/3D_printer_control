import logging
import time

from printer_server.threading_wrapper import Thread

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class XYStageDriver:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        super().__init__()
        self.initialized = None
        self.prev_x_position = None
        self.prev_y_position = None
        self.curr_x_position = None
        self.curr_y_position = None

    def setup_log_file(self, filename):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def logging_start(self):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def logging_stop(self):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def connect(self):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def initialize(self):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def home(self):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def getDefaultXYSpeed(self, axis=None):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def getDefaultXYAcceleration(self, axis=None):
        log.warning("Function not implemented. Using abstract XYStageDriver class")
        
    def getXYPosition(self, axis=None, notify=True):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def absMoveXY( self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def relMoveXY(self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def startXYJog(self, speed=None, acceleration=None, axis=None):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def stopXYJog(self, axis=None):
        if axis == "X":
            self.prev_x_position = round(self.getXYPosition(axis="X", notify=False), 4)
        elif axis == "Y":
            self.prev_y_position = round(self.getXYPosition(axis="Y", notify=False), 4)

    def getXYLimits(self, axis=None):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def setXYLimits(self, limits=None, axis=None):
        log.warning("Function not implemented. Using abstract XYStageDriver class")

    def initialize_and_positionXY(self, x, y):
        if self.initialized is None:
            self.initialized = False
            self.initialize()
            self.home()
            self.initialized = True

        while not self.initialized:
            time.sleep(0.1)

        time.sleep(0.25)

        for a in ["X", "Y"]:
            self.setXYLimits(axis=a)

        return self.threadedXYMove(log, x, y, join=True)

    def threadedXYMove(
        self,
        logger,
        x,
        y,
        join=True,
        speed_x=None,
        speed_y=None,
        acceleration_x=None,
        acceleration_y=None,
    ):
        """
        Starts multithreaded movement on both of the x/y axes. If any axis is set to none, it will not move.
        If join is set to true, the movements will join before returning
        """
        threads = [None, None]
        if x is not None:
            self.curr_x_position = round(x, 4)
            if self.curr_x_position != self.prev_x_position:
                threads[0] = Thread(
                    logger, 
                    name="xy_stage_driver_x_thread",
                    target=self.absMoveXY,
                    kwargs={
                        "mm": x,
                        "speed": speed_x,
                        "acceleration": acceleration_x,
                        "axis": "X",
                    },
                )
                threads[0].start()
        if y is not None:
            if hasattr(self, 'linked_focus_stage') and self.linked_focus_stage is not None:
                self.curr_y_position = round(y - self.linked_focus_stage.target_focus, 4)
            else:
                self.curr_y_position = round(y, 4)
            if self.curr_y_position != self.prev_y_position:
                threads[1] = Thread(
                    logger, 
                    name="xy_stage_driver_y_thread",
                    target=self.absMoveXY,
                    kwargs={
                        "mm": y,
                        "speed": speed_y,
                        "acceleration": acceleration_y,
                        "axis": "Y",
                    },
                )
                threads[1].start()
        if join:
            for thread in threads:
                if thread is not None:
                    thread.join()
                    if thread.exception is not None:
                        raise thread.exception
            return None
        else:
            return threads
