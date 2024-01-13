# FOCUS STAGE NEEDS TO RETURN POSITION IN UM

class FocusStageDriver:
    def __init__(self):
        
    def getFocusPosition(self, notify=True):

    def absMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):

    def relMoveFocus(self, mm, speed=None, acceleration=None, wait_for_settling=True):

    def startFocusJog(self, speed=None, acceleration=None):

    def stopFocusJog(self):

    def threadedFocusMove(
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
        if bp is not None:
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
        else:
            return thread