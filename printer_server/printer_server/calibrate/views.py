# -*- coding: utf-8 -*-
"""Control view."""
import os
# import imghdr
# import copy
from PIL import Image
from flask import Blueprint, request, render_template
# from datetime import datetime

from printer_server.settings import CalibrationConfig
from printer_server.hardware import printer3d
from printer_server.threads import calibrationThreads
from printer_server.extensions import socketio

# Create bluprint
blueprint = Blueprint('calibrate', __name__, url_prefix='/', static_folder='../static')

# Specify location of uploaded image and give default name
imagePath = os.path.join(CalibrationConfig.UPLOAD_FOLDER, 'calibration_images', 'temp.png')

# Decorator to handle navigation to calibration page
@blueprint.route('/calibrate')
def index():
    return render_template('calibrate.html')

# If hardware isn't initialized, initialize it
@socketio.on('initialize', namespace='/calibrate')
# pylint: disable=unused-argument
def initialize():
    if printer3d.state == 'uninitialized':
        calibrationThreads.initialize()
    else:
        socketio.emit('initialized', namespace='/calibrate', broadcast=True)

# Reset printer state, necessary if hardware has been powered down
@socketio.on('reset_printer_state', namespace='/calibrate')
# pylint: disable=unused-argument
def resetPrinterState(message):
    printer3d.state = 'uninitialized'

@socketio.on('galil_go_to_top', namespace='/calibrate')
# pylint: disable=unused-argument
def galil_go_to_top():
    calibrationThreads.goToZmax()

@socketio.on('galil_go_to_bottom', namespace='/calibrate')
# pylint: disable=unused-argument
def galil_go_to_bottom():
    calibrationThreads.goToZmin()

@socketio.on('calibration_motor', namespace='/calibrate')
def calibrationMotorMove(message):
    axis = message["axis"]
    distance = int(message["steps"])
    calibrationThreads.calibrationMotorMove(axis, distance)

@socketio.on('light_engine_stop', namespace='/calibrate')
# pylint: disable=unused-argument
def lightEngineStop():
    calibrationThreads.lightEngineStop()

@socketio.on('light_engine_start', namespace='/calibrate')
def lightEngineProject(message):
    calibrationThreads.lightEngineProject(
        imagePath,
        int(message["ledPower"]),
        int(message["repeat"]),
        int(message["exposure"]))

@blueprint.route('handle-calibration-upload', methods=['POST'])
def handleUpload():
    if 'file' in request.files:             # Check if the post request has the file part
        file = request.files['file']        # Get the file
        if file.filename != '' and file:    # File part of request actually has a file
            try:
                with Image.open(file) as pilImage:                          # Open file as PIL object
                    if pilImage.format == "PNG" and pilImage.mode == "L":   # Check imagePath format and mode
                        file.stream.seek(0)     # Seek to the beginning of file (fixes bug in Werkzeug file I\O)
                        file.save(imagePath)    # save it to the server
                        socketio.emit('calibration_image_uploaded', namespace='/calibrate', broadcast=True)
                        return ''
            except (OSError, FileNotFoundError):                            # File has big issues
                pass
    socketio.emit('calibration_image_bad', namespace='/calibrate', broadcast=True)
    return ''
