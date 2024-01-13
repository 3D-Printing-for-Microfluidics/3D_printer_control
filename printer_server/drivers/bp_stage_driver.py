
class BPStageDriver:
    def __init__(self):
        self.calibration_position = None
        self.bottom_position = None
        self.top_position = None

    def getBPPosition(self, notify=True):

    def absMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):

    def relMoveBP(self, mm, speed=None, acceleration=None, wait_for_settling=True):

    def startBPJog(self, speed=None, acceleration=None):

    def stopBPJog(self):

    def goToBPcalibration(self):

    def goToBPtop(self):

    def goToBPbottom(self):

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
        else:
            return thread