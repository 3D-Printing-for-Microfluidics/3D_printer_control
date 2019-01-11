# -*- coding: utf-8 -*-
"""Control view."""
import os
import imghdr
import copy 
from PIL import Image
from flask import Blueprint, request, render_template
from datetime import datetime

from printer_server.settings import CalibrationConfig
from printer_server.hardware import printer3d
from printer_server.threads import calibrationThreads
from printer_server.extensions import socketio

# Create bluprint 
blueprint = Blueprint('calibrate', __name__, url_prefix='/', static_folder='../static')

# Specify location of uploaded image and give default name 
imagePath = os.path.join(CalibrationConfig.UPLOAD_FOLDER, 'calibration_images','temp.png')

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

# Reset printer state, necessary if hardware has been powered down  
@socketio.on('reset_printer_state', namespace='/calibrate')
def resetPrinterState():
    printer3d.state = 'uninitialized'
  
@socketio.on('solus_go_to_top', namespace='/calibrate')
def solus_go_to_top():
    calibrationThreads.goToZmax()

@socketio.on('solus_go_to_bottom', namespace='/calibrate')
def solus_go_to_bottom():
    calibrationThreads.goToZmin()

@socketio.on('solus_move_Z', namespace='/calibrate')
def solusMoveZ(message):
    if all([message["direction"] != "UP", message["direction"] != "DOWN"]):
        return "Invalid direction value (Valid values are UP/DOWN)"
       
    return calibrationThreads.moveZ(message["direction"], message["distance"], message["speed"])

@socketio.on('calibration_motor', namespace='/calibrate')
def calibrationMotorMove(message):
    calibrationThreads.calibrationMotorMove(
                       message["axis"],
                       int(message["steps"]))

@socketio.on('light_engine_stop', namespace='/calibrate')
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


##############################
#          API               #
##############################

@blueprint.route("/calibrate/api", methods=['GET', 'POST'])
def api():
    try:
        if request.method == 'GET':
            callType = request.args.get("type")
            if callType  is None:
                return "Error: type not specified"
            elif callType == "printerStage":
                command = {"direction": request.args.get("direction"),
                        "distance": float(request.args.get("distance")),
                        "speed": int(request.args.get("speed"))}
                print(solusMoveZ(command)) # use this line in debug mode
                # return solusMoveZ(command) 
            elif callType == "calibrationStage":
                command = {"axis": request.args.get("axis"),
                        "steps": request.args.get("steps")}
                calibrationMotorMove(command)

            elif callType == "lightEngine":
                command = {"ledPower": request.args.get("power"), # led power
                        "repeat": request.args.get("repeat"), # repeated exposures
                        "exposure": request.args.get("exposure")} # exposure time (ms)
                lightEngineProject(command)
        else:
            fb = open(imagePath, 'wb')
            fb.write(request.data)
            fb.close()
    except Exception as e:
        return "Error: " + str(e)
    return "OK"