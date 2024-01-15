import logging
import time

from printer_server.threading_wrapper import Thread

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# FOCUS STAGE NEEDS TO RETURN POSITION IN UM

class FocusStageDriver:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.initialized = None

    def setup_log_file(self, filename):
        log.warn("Function not implemented. Using abstract FocusStageDriver class")

    def logging_start(self):
        log.warn("Function not implemented. Using abstract FocusStageDriver class")

    def logging_stop(self):
        log.warn("Function not implemented. Using abstract FocusStageDriver class")

    def connect(self, shutdown):
        log.warn("Function not implemented. Using abstract FocusStageDriver class")

    def initialize(self):
        log.warn("Function not implemented. Using abstract FocusStageDriver class")

    def home(self):
        log.warn("Function not implemented. Using abstract FocusStageDriver class")

    def getFocusPosition(self, notify=True):
        log.warn("Function not implemented. Using abstract FocusStageDriver class")

    def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        log.warn("Function not implemented. Using abstract FocusStageDriver class")

    def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        log.warn("Function not implemented. Using abstract FocusStageDriver class")

    def startFocusJog(self, speed=None, acceleration=None):
        log.warn("Function not implemented. Using abstract FocusStageDriver class")

    def stopFocusJog(self):
        log.warn("Function not implemented. Using abstract FocusStageDriver class")

    def initialize_and_positionFocus(self, pos):
        if self.initialized is None:
            self.initialized = False
            self.initialize()
            self.home()
            self.initialized = True

        while not self.initialized:
            time.sleep(0.1)

        return self.threadedFocusMove(log, pos, join=False)

    def threadedFocusMove(
        self,
        logger,
        mm,
        join=True,
        speed=None,
        acceleration=None
    ):
        """
        Starts threaded movement on focus axis. If any axis is set to none, it will not move.
        If join is set to true, the movements will join before returning
        """
        thread = None
        if mm is not None:
            thread = Thread(
                logger, 
                name="print_control_focus_thread",
                target=self.absMoveFocus,
                kwargs={
                    "mm": mm,
                    "speed": speed,
                    "acceleration": acceleration
                },
            )
            thread.start()
            if join:
                if thread is not None:
                    thread.join()
                return None
            else:
                return thread
        return None