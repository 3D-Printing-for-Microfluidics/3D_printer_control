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
from printer_server.hardware import printer3d
from printer_server.hardware import calibrationControl


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
        self.calibrationControl = calibrationControl
        self._thread = threading.Thread()
        
    @thread_decorator('initialized', 'Initialization complete')
    def initialize(self):
        """Establish USB connection with Solus, and find zero in Z 
        axis for build platform.
        """
        self.projector.connect()
        self.solus.connect()
        self.solus.initialize()

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

    @thread_decorator('calibration_motor_done', 'Calibration move done')
    def calibration_motor_move(self, axis, steps):
        """calibration_motor_move -- Move specified calibration 
        motor by specified number of steps
        """
        self.calibrationControl.move(axis, steps)
           
    @property
    def isBusy(self):
        """boolean -- whether the printer is printing"""
        return self._thread.isAlive()
