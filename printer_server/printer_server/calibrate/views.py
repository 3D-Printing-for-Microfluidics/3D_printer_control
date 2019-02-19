# -*- coding: utf-8 -*-
"""Control view."""
import os
import imghdr
import copy
import json
from PIL import Image
from flask import Blueprint, request, render_template
from datetime import datetime

from printer_server.settings import CalibrationConfig
from printer_server.config import printer3d, calibrationStageTypes, stageDisplayOrder, savedPos, saveParamsToDisk
from printer_server.threads import calibrationThreads
from printer_server.extensions import socketio

# Create bluprint
blueprint = Blueprint('calibrate', __name__, url_prefix='/', static_folder='../static')

# Specify location of uploaded image and give default name
imagePath = os.path.join(CalibrationConfig.UPLOAD_FOLDER, 'calibration_images','temp.png')

# local copy of saved positions
savedPositions = copy.deepcopy(savedPos)

# Decorator to handle navigation to calibration page
@blueprint.route('/calibrate')
def index():
    jsonStageOrder = json.dumps(calibrationStageTypes)
    return render_template('calibrate.html', stages=calibrationStageTypes, stageOrder=stageDisplayOrder, jsonStageOrder=jsonStageOrder)

# If hardware isn't initialized, initialize it
@socketio.on('initialize', namespace='/calibrate')
def initialize(message):
    # if printer3ds.state is 'uninitialized':
    calibrationThreads.initialize(message)
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
    calibrationThreads.setRelative()
    return calibrationThreads.moveZ(message["direction"], float(message["distance"]), int(message["speed"]))

@socketio.on('home', namespace='/calibrate')
def home(message):
    calibrationThreads.stageHome(message)

@socketio.on('calibration_motor', namespace='/calibrate')
def calibrationMotorMove(message):
    calibrationThreads.calibrationStageMove(
                       message["axis"],
                       int(message["steps"]))

@socketio.on('set_relative', namespace='/calibrate')
def calibrationSetRelative(message):
    calibrationThreads.setRelative(stage=message["stage"])

@socketio.on('set_absolute', namespace='/calibrate')
def calibrationSetAbsolute(message):
    calibrationThreads.setAbsolute(stage=message["stage"])

@socketio.on('calibration_get_position', namespace='/calibrate')
def calibrateGetPosition(stage):
    position = calibrationThreads.calibrationStageGetPos(stage)
    socketio.emit("calibration_stage_position", {"pos": position, "stage": stage}, namespace='/calibrate', broadcast=True)

@socketio.on('goto_saved_pos', namespace='/calibrate')
def calibrationGoToSavedPos(stage):
    calibrationThreads.calibrationStageMove(stage, savedPositions[stage] * 1000)  # translate from mm to um

@socketio.on('save_current_position', namespace='/calibrate')
def saveCurrentPosition(stage):
    position = calibrationThreads.calibrationStageGetPos(stage)
    savedPositions[stage] = position
    saveParamsToDisk(savedPositions)
    socketio.emit("last_saved_pos", position)

@socketio.on('get_saved_position', namespace='/calibrate')
def getSavedPosition(stage):
    socketio.emit("saved_position", {"stage": stage, "pos": savedPositions[stage]}, namespace='/calibrate', broadcast=True)

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

@blueprint.route("/calibrate/api/initialize", methods=['GET', 'POST'])
def apiInit():
    print("api-initialized")
    try:
        if printer3d.state is 'uninitialized':
            calibrationThreads.initialize()
    except Exception as e:
        return "Error: " + str(e)
    return "OK"

@blueprint.route("/calibrate/api/printerStage", methods=['GET'])
def apiPrinterStage(): 
    print("Moving z stage")
    try:
        command = {"direction": request.args.get("direction"),
                "distance": float(request.args.get("distance")),
                "speed": int(request.args.get("speed"))}
        calibrationThreads.setAbsolute()
        print(solusMoveZ(command)) # use this line in debug mode
        # return solusMoveZ(command)
    except Exception as e:
        return "Error: " + str(e)
    return "OK"

@blueprint.route("/calibrate/api/calibrationStageMove", methods=['GET'])
def apiCalibrationStageMove():
    try:
        command = {"stage": request.args.get("axis"),
                "steps": int(request.args.get("steps"))}
        calibrationThreads.calibrationStageMove(**command)
    except Exception as e:
        return "Error: " + str(e)
    return "OK"

@blueprint.route("/calibrate/api/home", methods=['GET'])
def calibrationHome():
    try:
        command = {"stage": request.args.get("axis")}
        if command["stage"] == "solus":
            calibrationThreads.solus_home()
        else:
            calibrationThreads.calibrationStageHome(**command)
    except Exception as e:
        return "Error: " + str(e)
    return "OK"

@blueprint.route("/calibrate/api/calibrationStageGetPosition", methods=['GET'])
def calibrationStageGetPosition():
    if printer3d.state is 'uninitialized':
        return "Error: printer not initialized"
    try:
        command = {"stage": request.args.get("axis")}
        position = calibrationThreads.calibrationStageGetPos(**command)
        return str(position)
    except Exception as e:
        return "Error: " + str(e)

@blueprint.route("/calibrate/api/calibrationStage/setMode", methods=['GET'])
def apiCalibrationStageSetMode():
    try:
        if request.args.get("type") == "relative":
            calibrationThreads.setRelative(request.args.get("axis"))
        elif request.args.get("type") == "absolute":
            calibrationThreads.setAbsolute(request.args.get("axis"))
        else:
            raise Exception
    except Exception as e:
        return "Error: " + str(e)
    return "OK"


@blueprint.route("/calibrate/api/lightEngine", methods=['GET', 'POST'])
def apiLightEngine():
    print("Light engine turned on")
    try:
        if request.method == 'GET':
            calltype = request.args.get("type")
            if calltype == "start":
                command = {"ledPower": int(request.args.get("power")), # led power
                        "repeat": int(request.args.get("repeat")), # repeated exposures
                        "exposure": int(request.args.get("exposure"))} # exposure time (ms)
                lightEngineProject(command)
            else:
                lightEngineStop()
        else:
            fb = open(imagePath, 'wb')
            fb.write(request.data)
            fb.close()
    except Exception as e:
        return "Error: " + str(e)
    return "OK"
