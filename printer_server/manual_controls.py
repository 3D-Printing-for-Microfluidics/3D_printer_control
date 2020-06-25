# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime
from printer_server.extensions import socketio
from printer_server.hardware import printer3d


class ManualControls:
    """The manualControls class contains all the individual
    3D printer hardware operations.
    """
    def __init__(self):
        self.printer3d = printer3d
        self.galil = printer3d.galil
        self.projector = printer3d.projector
        self.tiptilt = printer3d.tiptilt
        self.kdc = printer3d.kdc
        self._thread = None
        self.calibration_mode = False
        self.position_log_file = str(Path.cwd() / 'logs' / 'calibration_position_log.txt')

    def write_to_position_log(self, message):
        with open(self.position_log_file, "a") as f:
            f.write("{} {}\n".format(datetime.now().strftime('%Y-%m-%d_%H-%M-%S'), message))
            
    def setCalibrationMode(self, mode):
        """setCalibrationMode -- Sets the variable determining if printer can be auto-calibrated"""
        self.calibration_mode = mode
    
    def getCalibrationMode(self):
        """getCalibrationMode -- Returns the variable determining if printer can be auto-calibrated"""
        message = {
            "mode": self.calibration_mode
        }
        socketio.emit('calibration_mode', message, namespace='/calibrate', broadcast=True)

    def goToZmax(self):
        """goToZmax -- Move main Z stage to max position (up)"""
        self.galil.goToZmax()
        socketio.emit('galil_done', namespace='/calibrate', broadcast=True)

    def goToZmin(self):
        """goToZmin -- Move main z stage to min position (down)"""
        self.galil.goToZmin()
        socketio.emit('galil_done', namespace='/calibrate', broadcast=True)

    def home(self):
        """home -- Home main z stage"""
        self.galil.home()
        socketio.emit('galil_done', namespace='/calibrate', broadcast=True)

    def moveGalil(self, mode, distance, speed, acceleration):
        """Move the main Z stage. All units in mm"""
        if mode == "absolute":
            self.galil.absMove(mm=distance, speed=speed, acceleration=acceleration)
        elif mode == "relative":
            self.galil.relMove(mm=distance, speed=speed, acceleration=acceleration)
        socketio.emit('galil_done', namespace='/calibrate', broadcast=True)
        
    def startJogGalil(self, speed):
        """Start """
        self.galil.startJog(speed=speed)
        #socketio.emit('galil_done', namespace='/calibrate', broadcast=True)
    
    def stopJogGalil(self):
        """Stop jogging the main Z stage"""
        self.galil.stopJog()
        socketio.emit('galil_done', namespace='/calibrate', broadcast=True)

    def getPositionGalil(self):
        """Move the main Z stage. All units in mm"""
        message = {
            "position": self.galil.cntsToMm(self.galil.getPosition())
        }
        socketio.emit('galil_position', message, namespace='/calibrate', broadcast=True)

    def calibrationMotionComplete(self):
        message = {
            "tip": self.printer3d.tiptilt.get_position("Tip"),
            "tilt": self.printer3d.tiptilt.get_position("Tilt"),
            "distance": self.printer3d.kdc.getCurrentPos()
        }
        self.write_to_position_log(message)
        socketio.emit('calibration_motor_move_complete', message, namespace='/calibrate', broadcast=True)

    def homeCalibrationMotor(self, axis):
        if axis == "Distance":
            self.printer3d.kdc.home()
        else:
            self.printer3d.tiptilt.home()
        self.calibrationMotionComplete()

    def moveCalibrationMotor(self, axis, um, mode, fast):
        mode = mode != "absolute" # convert mode to True/False, absolute is true, all else is false
        if axis == "Distance":
            self.printer3d.kdc.move(um, relative=mode)
        else:
            self.printer3d.tiptilt.move(axis, um, relative=mode, fast=fast)
        self.calibrationMotionComplete()

    def lightEngineStop(self):
        """lightEngineStop -- Turn off the LED in the light engine"""
        self.projector.stop_sequencer()
        self.projector.screenThread.screen.clear()
        socketio.emit('light_engine_stop_complete', namespace='/calibrate', broadcast=True)

    def lightEngineProject(self, image, ledPower, repeat, exposure):
        """lightEngineProject -- Project the image with the given settings"""
        self.projector.project(image, exposure, ledPower, repeat)
        if repeat:      # repeat == 1 means show once, == 0 means repeat forever
            self.projector.screenThread.screen.clear()
        socketio.emit('light_engine_start_complete', namespace='/calibrate', broadcast=True)
