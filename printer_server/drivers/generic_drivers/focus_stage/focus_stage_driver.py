import logging
import time

from printer_server.threading_wrapper import Thread

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# FOCUS STAGE NEEDS TO RETURN POSITION IN UM

class FocusStageDriver:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        super().__init__()
        self.initialized = None
        self.connected = None
        self.prev_focus_position = None

    def setup_log_file(self, filename):
        log.warning("Function not implemented. Using abstract FocusStageDriver class")

    def logging_start(self):
        log.warning("Function not implemented. Using abstract FocusStageDriver class")

    def logging_stop(self):
        log.warning("Function not implemented. Using abstract FocusStageDriver class")

    def connect(self):
        log.warning("Function not implemented. Using abstract FocusStageDriver class")

    def initialize(self):
        log.warning("Function not implemented. Using abstract FocusStageDriver class")

    def home(self):
        log.warning("Function not implemented. Using abstract FocusStageDriver class")

    def getDefaultFocusSpeed(self):
        log.warning("Function not implemented. Using abstract FocusStageDriver class")

    def getDefaultFocusAcceleration(self):
        log.warning("Function not implemented. Using abstract FocusStageDriver class")

    def getFocusPosition(self, notify=True):
        log.warning("Function not implemented. Using abstract FocusStageDriver class")

    # def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
    #     log.warning("Function not implemented. Using abstract FocusStageDriver class")

    # def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):
    #     log.warning("Function not implemented. Using abstract FocusStageDriver class")

    def startFocusJog(self, speed=None, acceleration=None):
        log.warning("Function not implemented. Using abstract FocusStageDriver class")

    def stopFocusJog(self):
        self.prev_focus_position = round(self.getFocusPosition(notify=False), 4)

    def getFocusLimits(self):
        log.warning("Function not implemented. Using abstract FocusStageDriver class")

    def setFocusLimits(self, limits=None):
        log.warning("Function not implemented. Using abstract FocusStageDriver class")

    def initialize_and_positionFocus(self, pos):
        if self.initialized is None:
            self.initialized = False
            self.initialize()
            self.home()
            self.initialized = True

        while not self.initialized:
            time.sleep(0.1)

        self.setFocusLimits()

        return self.threadedFocusMove(log, pos, join=True)

    def threadedFocusMove(
        self,
        logger,
        mm,
        relative=False, 
        speed=None,
        acceleration=None,
        wait_for_settling=True,
        join=True,
    ):
        """
        Starts threaded movement on focus axis. If any axis is set to none, it will not move.
        If join is set to true, the movements will join before returning
        """
        thread = None
        if mm is not None:
            if relative:
                current_pos = round(self.prev_focus_position + mm, 4)
                target = self.relMoveFocus
            else:
                current_pos = round(mm, 4)
                target = self.absMoveFocus

            if current_pos != self.prev_focus_position:
                thread = Thread(
                    logger, 
                    name="focus_stage_driver_thread",
                    target=target,
                    kwargs={
                        "mm": round(mm, 4),
                        "speed": speed,
                        "acceleration": acceleration,
                        "wait_for_settling": wait_for_settling,
                    },
                )
                thread.start()
            if join:
                if thread is not None:
                    thread.join()
                    if thread.exception is not None:
                        raise thread.exception
                return None
            else:
                return thread
        return None