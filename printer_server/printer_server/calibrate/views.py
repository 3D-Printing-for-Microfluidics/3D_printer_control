# -*- coding: utf-8 -*-
"""Control view."""
import os
from flask import Blueprint, request, render_template
from datetime import datetime

from printer_server.settings import CalibrationConfig
from printer_server.hardware import printer3d
from printer_server.threads import calibrationThreads
from printer_server.extensions import socketio

# Create bluprint 
blueprint = Blueprint('calibrate', __name__, url_prefix='/', static_folder='../static')

# Specify location of uploaded image 
image = os.path.join(CalibrationConfig.UPLOAD_FOLDER, 'calibration_images','temp.png')

# Decorator to handle navigation to calibration page 
@blueprint.route('/calibrate')
def index():
    return render_template('calibrate.html')

# If hardware isn't initialized, initialize it 
@socketio.on('initialize', namespace='/calibrate')
def initialize():
    if printer3d.state is 'uninitialized':
        calibrationThreads.initialize()
    else: 
        socketio.emit('initialized', namespace='/calibrate', broadcast=True)
        
@socketio.on('solus_go_to_top', namespace='/calibrate')
def solus_go_to_top():
    calibrationThreads.goToZmax()

@socketio.on('solus_go_to_bottom', namespace='/calibrate')
def solus_go_to_bottom():
    calibrationThreads.goToZmin()

@socketio.on('calibration_motor', namespace='/calibrate')
def calibrationMotorMove(message):
    calibrationThreads.calibrationMotorMove(
                       message["axis"],
                       message["steps"])

@socketio.on('light_engine_stop', namespace='/calibrate')
def lightEngineStop():
    calibrationThreads.lightEngineStop()

@socketio.on('light_engine_start', namespace='/calibrate')
def lightEngineProject(message):
    calibrationThreads.lightEngineProject(
                       image, 
                       int(message["ledPower"]),
                       int(message["repeat"]),
                       int(message["exposure"]))

@blueprint.route('handle-calibration-upload', methods=['POST'])
def handleUpload():
    file = request.files.getlist('file')[0]
    file.save(image)
    socketio.emit('calibration_image_uploaded', namespace='/calibrate', broadcast=True)
    return ''   # this line is requred as a response must be returned 
