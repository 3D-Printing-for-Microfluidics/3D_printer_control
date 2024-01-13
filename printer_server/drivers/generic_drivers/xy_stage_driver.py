
class XYStageDriver:
    def __init__(self):
        
    def getXYPosition(self, axis=None, notify=True):

    def absMoveXY( self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):

    def relMoveXY(self, mm=None, speed=None, acceleration=None, wait_for_settling=True, axis=None):

    def startXYJog(self, speed=None, acceleration=None, axis=None):

    def stopXYJog(self, axis=None):

    def threadedXYMove(
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
        else:
            return threads