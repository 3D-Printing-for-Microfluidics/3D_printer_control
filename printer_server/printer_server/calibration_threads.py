# -*- coding: utf-8 -*-
"""
All the printer operations involve physical movement of certain 
parts in the 3D printer. Therefore, it makes sense to throw them 
into another thread such that the server stays responsive. This 
is achieved by using :py:class:`CalibrationThreads`.
"""


import threading
from datetime import datetime
from functools import wraps
import os

from printer_server.extensions import socketio
from printer_server.config import printer3d, calibrationStages
 

def thread_decorator(state, text):
    """Make decorators for the printer operation methods. 
    The wrapped methods will push the 3D printer state changes 
    to clients, and finish the operations in another thread. 
    
    :param str state: what will be emitted when operation is complete 
    :param str text: printer message for the message box in webpage

    Before::
    
        def operation(self):
            # code for operation #
    
    After::
    
        def operation(self):
    
            def func(*args, **kwargs):
                # code for operation #
                printer3d.state = 'initialized'
                socketio.emit(printer3d.state, {}, namespace='/calibration', broadcast=True)
    
            printer3d.state = 'busy'
            message = {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'text': text
            }
            socketio.emit(printer3d.state, message, namespace='/calibration', broadcast=True)
            _thread = threading.Thread(target=func, args=(*args, ), kwargs={**kwargs, })
            _thread.start()
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            def func(*args, **kwargs):
                f(*args, **kwargs)
                printer3d.state = state
                socketio.emit(printer3d.state, dict(), namespace='/calibrate', broadcast=True)
            
            printer3d.state = 'busy'
            message = {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'text': text
            }
            socketio.emit(printer3d.state, message, namespace='/calibrate', broadcast=True)
            _thread = threading.Thread(target=func, args=(*args, ), kwargs={**kwargs, })
            _thread.start()
            
        return decorated_function
        
    return decorator


class CalibrationThreads:
    """The CalibrationThreads class contains all the individual 
    3D printer hardware operations . It wraps the ``threading.Thread``
    object such that a new thread is instantiated every time the 3D 
    printer starts an operation. This is because the native Python 
    ``threading.Thread`` object can only be started once. Threading 
    the hardware control keeps the UI responsive.    
    """
    def __init__(self):
        self.printer3d = printer3d
        self.solus = printer3d.solus
        self.projector = printer3d.projector

        self.calibrationStages = calibrationStages  

        self._thread = threading.Thread()
        
    @thread_decorator('initialized', 'Initialization complete')
    def initialize(self, stage):
        """Establish USB connection with Solus, and find zero in Z 
        axis for build platform.
        """
        if stage == "solus":
            self.solus.connect()
        elif stage == "le":
            self.projector.connect()
        else:
            self.calibrationStages[stage].initialize()

    @thread_decorator('solus_done', 'Solus go to Z max')
    def goToZmax(self):
        """goToZmax -- Move main Z stage to max position (up)
        """
        self.solus.goToZmax()

    @thread_decorator('solus_done', 'Solus go to Z min')
    def goToZmin(self):
        """goToZmin -- Move main z stage to min position (down)
        """
        self.solus.goToZmin()

    @thread_decorator('solus_done', 'Solus moved Z axis')
    def moveZ(self, direction, distance, speed):
        """goToZmin -- Move main z stage to min position (down)
        """
        print("direction: {} {} distance: {} {} speed: {} {}".format(direction, type(direction),
                                                                     distance, type(distance),
                                                                     speed, type(speed)))
        return self.solus.moveZ(direction, distance, speed)

    @thread_decorator("solus_done", "Solus set to relative mode")
    def setRelative(self, stage="solus"):
        """Set the stage to relative mode"""
        if stage == "solus":
            return self.solus.send("G91")
        else:
            return self.calibrationStages[stage].setRelative()

    @thread_decorator("solus_done", "Solus set to absolute mode")
    def setAbsolute(self, stage="solus"):
        """Set the stage to absolute mode"""
        if stage == "solus":
            return self.solus.send("G90")
        else:
            return self.calibrationStages[stage].setAbsolute()

    @thread_decorator('calibration_motor_done', 'Calibration move done')
    def calibrationStageMove(self, stage, steps):
        """calibrationMotorMove -- Move specified calibration 
        motor by specified number of steps
        """
        print(stage, " ", steps)
        self.calibrationStages[stage].move(steps)
           
    @thread_decorator('light_engine_stop_complete', 'Light engine stopped')
    def lightEngineStop(self):
        """lightEngineStop -- Turn off the LED in the light engine 
        """
        self.projector.stop()
        self.projector.clear()

    @thread_decorator('light_engine_start_complete', 'Light engine started')
    def lightEngineProject(self, image, ledPower, repeat, exposure):
        """lightEngineProject -- Project the image with the given settings 
        """
        self.projector.calibrateProject(image, ledPower, repeat, exposure)
        if repeat:      # repeat == 1 means show once, == 0 means repeat forever  
            self.projector.clear()


    @thread_decorator("stage_homed", "Calibration stage homed")
    def stageHome(self, stage):
        if stage == "solus":
            self.solus.initialize()
        else:
            self.calibrationStages[stage].home()

    def calibrationStageGetPos(self, stage):
        pos = self.calibrationStages[stage].getCurrentPos()
        return pos


    @property
    def isBusy(self):
        """boolean -- whether the printer is printing"""
        return self._thread.isAlive()
