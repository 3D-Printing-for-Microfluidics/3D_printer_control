import logging
import time

from printer_server.threading_wrapper import Thread

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class XYStageDriver:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.initialized = None

    def setup_log_file(self, filename):
        log.warn("Function not implemented. Using abstract XYStageDriver class")

    def logging_start(self):
        log.warn("Function not implemented. Using abstract XYStageDriver class")

    def logging_stop(self):
        log.warn("Function not implemented. Using abstract XYStageDriver class")

    def connect(self, shutdown):
        log.warn("Function not implemented. Using abstract XYStageDriver class")

    def initialize(self):
        log.warn("Function not implemented. Using abstract XYStageDriver class")

    def home(self):
        log.warn("Function not implemented. Using abstract XYStageDriver class")
        
    def getXYPosition(self, axis=None, notify=True):
        log.warn("Function not implemented. Using abstract XYStageDriver class")

    def absMoveXY( self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        log.warn("Function not implemented. Using abstract XYStageDriver class")

    def relMoveXY(self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):
        log.warn("Function not implemented. Using abstract XYStageDriver class")

    def startXYJog(self, speed=None, acceleration=None, axis=None):
        log.warn("Function not implemented. Using abstract XYStageDriver class")

    def stopXYJog(self, axis=None):
        log.warn("Function not implemented. Using abstract XYStageDriver class")

    def initialize_and_positionXY(self, x, y):
        if self.initialized is None:
            self.initialized = False
            self.initialize()
            self.home()
            self.initialized = True

        while not self.initialized:
            time.sleep(0.1)

        return self.threadedXYMove(log, x, y, join=False)

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
            threads[0] = Thread(
                logger, 
                name="print_control_x_thread",
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
            threads[1] = Thread(
                logger, 
                name="print_control_y_thread",
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
            return None
        else:
            return threads
