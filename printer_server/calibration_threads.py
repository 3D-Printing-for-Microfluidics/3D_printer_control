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
# import os

from printer_server.extensions import socketio
from printer_server.hardware import printer3d
# from printer_server.hardware import calibrationControl


# pylint: disable=unused-argument
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
                # printer3d.state = state
                socketio.emit(printer3d.state, dict(), namespace='/calibrate', broadcast=True)

            # printer3d.state = 'busy'
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
        self.galil = printer3d.galil
        self.projector = printer3d.projector
        self.tiptilt = printer3d.tiptilt
        self.kdc = printer3d.kdc
        self._thread = None

    @thread_decorator('galil_done', 'Galil go to Z max')
    def goToZmax(self):
        """goToZmax -- Move main Z stage to max position (up)
        """
        self.galil.goToZmax()
        print("sent galil done")

    @thread_decorator('galil_done', 'Galil go to Z min')
    def goToZmin(self):
        """goToZmin -- Move main z stage to min position (down)
        """
        self.galil.goToZmin()
        print("sent galil done")

    @thread_decorator('galil_done', 'Galil go to Z min')
    def home(self):
        """home -- Home main z stage
        """
        self.galil.home()
        print("sent galil done")

    @thread_decorator('calibration_motor_done', 'Calibration move done')
    def calibrationMotorMove(self, axis, um):
        """calibrationMotorMove -- Move specified calibration
        motor by specified number of steps
        """
        print("axis:{}, dist:{}".format(axis, um))
        if axis == "Distance":
            self.printer3d.kdc.move(um)
        else:
            self.printer3d.tiptilt.move(axis, um)

    @thread_decorator('distance_abs_move_done', 'Distance absolute move done')
    def distanceAbsMove(self, um):
        """distanceAbsMove -- Move the distance to the specified position
        """
        self.printer3d.kdc.setAbsolute()
        self.printer3d.kdc.move(um)
        self.printer3d.kdc.setRelative()

    @thread_decorator('tip_abs_move_done', 'Tip absolute move done')
    def tipAbsMove(self, um):
        """tipAbsMove -- Move the tip to the specified position
        """
        print(um)
        self.printer3d.tiptilt.move("Tip", um, relative=False)

    @thread_decorator('tilt_abs_move_done', 'Tilt absolute move done')
    def tiltAbsMove(self, um):
        """tiltAbsMove -- Move the tilt to the specified position
        """
        print(um)
        self.printer3d.tiptilt.move("Tilt", um, relative=False)

    @thread_decorator('light_engine_stop_complete', 'Light engine stopped')
    def lightEngineStop(self):
        """lightEngineStop -- Turn off the LED in the light engine
        """
        self.projector.stop_sequencer()
        self.projector.screenThread.screen.clear()

    @thread_decorator('home_tip_complete', 'Tip homed')
    def homeTipAxis(self):
        """homeTipAxis - Home the tip axis
        """
        self.tiptilt.home()

    @thread_decorator('home_tilt_complete', 'Tilt homed')
    def homeTiltAxis(self):
        """homeTiltAxis - Home the tip axis
        """
        self.tiptilt.home()

    @thread_decorator('home_dist_complete', 'Distance homed')
    def homeDistanceAxis(self):
        """homeDistanceAxis - Home the tip axis
        """
        self.kdc.home()

    @thread_decorator('light_engine_start_complete', 'Light engine started')
    def lightEngineProject(self, image, ledPower, repeat, exposure):
        """lightEngineProject -- Project the image with the given settings
        """
        self.projector.project(image, exposure, ledPower, repeat)
        if repeat:      # repeat == 1 means show once, == 0 means repeat forever
            self.projector.screenThread.screen.clear()

    @property
    def isBusy(self):
        """boolean -- whether the printer is printing"""
        return self._thread.isAlive()
