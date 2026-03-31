import logging
import time

from printer_server.threading_wrapper import Thread

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class BPStageDriver:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        super().__init__()
        self.initialized = None
        self.calibration_position = None
        self.bottom_position = None
        self.top_position = None

    def setup_log_file(self, filename):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def logging_start(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def logging_stop(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def get_logging_results(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def connect(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def initialize(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def home(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def getDefaultBPSpeed(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def getDefaultBPAcceleration(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def getBPPosition(self, notify=True):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def absMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def relMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def startBPJog(self, speed=None, acceleration=None):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def stopBPJog(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def goToBPcalibration(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def goToBPtop(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def goToBPbottom(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def getBPLimits(self):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def setBPLimits(self, limits=None):
        log.warning("Function not implemented. Using abstract BPStageDriver class")

    def initialize_and_positionBP(self, pos, external_control_enabled):
        if self.initialized is None:
            self.initialized = False
            self.initialize()
            self.home()
            self.initialized = True

        while not self.initialized:
            time.sleep(0.1)

        if external_control_enabled:
            self.setBPLimits("calibration")
        else:
            self.setBPLimits()

        return self.threadedBPMove(log, pos, join=True)

    def threadedBPMove(
        self,
        logger,
        mm,
        join=True,
        speed=None,
        acceleration=None
    ):
        """
        Starts threaded movement on bp axis. If any axis is set to none, it will not move.
        If join is set to true, the movements will join before returning
        """
        thread = None
        if mm is not None:
            thread = Thread(
                logger, 
                name="bp_stage_driver_thread",
                target=self.absMoveBP,
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
                    if thread.exception is not None:
                        raise thread.exception
                return None
            else:
                return thread
        return None