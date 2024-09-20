import time
import logging

from printer_server.threading_wrapper import Thread

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class TTRStageDriver:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        super().__init__()
        self.initialized = None

    def connect(self):
        log.warning("Function not implemented. Using abstract TTRStageDriver class")

    def initialize(self):
        log.warning("Function not implemented. Using abstract TTRStageDriver class")

    def home(self):
        log.warning("Function not implemented. Using abstract TTRStageDriver class")

    def getTTRPosition(self, axis=None, notify=True):
        log.warning("Function not implemented. Using abstract TTRStageDriver class")

    def absMoveTTR(self, rad=None, axis=None):
        log.warning("Function not implemented. Using abstract TTRStageDriver class")

    def relMoveTTR(self, rad=None, axis=None):
        log.warning("Function not implemented. Using abstract TTRStageDriver class")

    def initialize_and_positionTTR(self, tip, tilt, rotate):
        if self.initialized is None:
            self.initialized = False
            self.initialize()
            if self.config_dict.get("auto_repositioning", True):
                self.home()
            self.initialized = True

        while not self.initialized:
            time.sleep(0.1)

        if self.config_dict.get("auto_repositioning", True):
            return self.threadedTTRMove(log, tip, tilt, rotate, join=True)
        return True
    
    def threadedTTRMove(
        self,
        logger,
        tip,
        tilt,
        rotate,
        join=True
    ):
        """
        Starts multithreaded movement on both of the x/y axes. If any axis is set to none, it will not move.
        If join is set to true, the movements will join before returning
        """
        threads = [None, None, None]
        if tip is not None:
            threads[0] = Thread(
                logger, 
                name="ttr_stage_driver_tip_thread",
                target=self.absMoveTTR,
                kwargs={
                    "rad": tip,
                    "axis": "Tip",
                },
            )
            threads[0].start()
        if tilt is not None:
            threads[1] = Thread(
                logger, 
                name="ttr_stage_driver_tilt_thread",
                target=self.absMoveTTR,
                kwargs={
                    "rad": tilt,
                    "axis": "Tilt",
                },
            )
            threads[1].start()
        if rotate is not None:
            threads[2] = Thread(
                logger, 
                name="ttr_stage_driver_rotate_thread",
                target=self.absMoveTTR,
                kwargs={
                    "rad": rotate,
                    "axis": "Rotate",
                },
            )
            threads[2].start()
        if join:
            for thread in threads:
                if thread is not None:
                    thread.join()
            return None
        else:
            return threads