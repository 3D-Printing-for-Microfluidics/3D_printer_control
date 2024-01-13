import logging
import time

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class BPStageDriver:
    def __init__(self):
        self.initialized = None
        self.calibration_position = None
        self.bottom_position = None
        self.top_position = None

    def setup_log_file(self, filename):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def logging_start(self):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def logging_stop(self):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def connect(self, shutdown):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def initialize(self):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def home(self):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def initialize_and_positionBP(self, pos, join=True):
        if self.initialized is None:
            self.initialized = False
            self.initialize()
            self.home()

        while not self.initialized:
            time.sleep(0.1)

        return self.threadedBPMove(log, pos, join=join)

    def getBPPosition(self, notify=True):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def absMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def relMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def startBPJog(self, speed=None, acceleration=None):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def stopBPJog(self):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def goToBPcalibration(self):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def goToBPtop(self):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def goToBPbottom(self):
        log.warn("Function not implemented. Using abstract BPStageDriver class")

    def threadedBPMove(
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
        if bp is not None:
            thread = Thread(
                logger, 
                name="print_control_bp_thread",
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
            return None
        else:
            return thread