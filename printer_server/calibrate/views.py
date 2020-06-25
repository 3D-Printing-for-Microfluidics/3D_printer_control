# -*- coding: utf-8 -*-
"""Control view."""
import os
# import imghdr
# import copy
from PIL import Image
from flask import Blueprint, request, render_template
# from datetime import datetime

from printer_server.extensions import socketio
from printer_server.settings import CalibrationConfig
from printer_server.threads import manualControls

# Create bluprint
blueprint = Blueprint('calibrate', __name__, url_prefix='/', static_folder='../static')

# Specify location of uploaded image and give default name
imagePath = os.path.join(CalibrationConfig.UPLOAD_FOLDER, 'calibration_images', 'temp.png')

# Decorator to handle navigation to calibration page
@blueprint.route('/calibrate')
def index():
    return render_template('calibrate.html')
    
@socketio.on('set_calibration_mode', namespace='/calibrate')
def set_calibration_mode(message):
    mode = message["mode"]
    manualControls.getCalibrationMode(mode)
    
@socketio.on('get_calibration_mode', namespace='/calibrate')
def get_calibration_mode():
    manualControls.getCalibrationMode()

@socketio.on('galil_go_to_top', namespace='/calibrate')
def galil_go_to_top():
    manualControls.goToZmax()

@socketio.on('galil_go_to_bottom', namespace='/calibrate')
def galil_go_to_bottom():
    manualControls.goToZmin()

@socketio.on('galil_home', namespace='/calibrate')
def home():
    manualControls.home()

@socketio.on("galil_move", namespace="/calibrate")
def galil_move(message):
    #manualControls.home()
    mode = message["mode"]
    speed = float(message["speed"])
    distance = float(message["distance"])
    acceleration = float(message["acceleration"])
    manualControls.moveGalil(mode, distance, speed, acceleration)
    
@socketio.on("galil_start_jog", namespace="/calibrate")
def galil_startJog(message):
    speed = float(message["speed"])
    manualControls.startJogGalil(speed)
    
@socketio.on("galil_stop_jog", namespace="/calibrate")
def galil_stopJog():
    manualControls.stopJogGalil()

@socketio.on("galil_get_position", namespace="/calibrate")
def galil_get_position():
    manualControls.getPositionGalil()

@socketio.on('calibration_motor_move', namespace='/calibrate')
def moveCalibrationMotor(message):
    axis = message["axis"]
    distance = float(message["microns"])
    mode = message["mode"]
    fast = message["fast"]
    manualControls.moveCalibrationMotor(axis, distance, mode, fast)

@socketio.on('calibration_motor_home', namespace='/calibrate')
def homeCalibrationMotor(message):
    axis = message["axis"]
    manualControls.homeCalibrationMotor(axis)

@socketio.on('light_engine_stop', namespace='/calibrate')
def lightEngineStop():
    manualControls.lightEngineStop()

@socketio.on('light_engine_start', namespace='/calibrate')
def lightEngineProject(message):
    manualControls.lightEngineProject(
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
