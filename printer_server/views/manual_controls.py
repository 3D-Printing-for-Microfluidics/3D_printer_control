# -*- coding: utf-8 -*-
"""Control view."""
import os

from pathlib import Path
from datetime import datetime
from PIL import Image
from flask import Blueprint, request, render_template

from printer_server.extensions import socketio
from printer_server.settings import CalibrationConfig
from printer_server.hardware import printer3d


class External_Control:
    def __init__(self):
        self.enable_flag = False

    def set_enable(self, status):
        self.enable_flag = status

    def get_enable(self):
        return self.enable_flag


galil = printer3d.galil
projector = printer3d.projector
tiptilt = printer3d.tiptilt
kdc = printer3d.kdc
external_control_enable = External_Control()
position_log_file = str(Path.cwd() / "logs" / "calibration_position_log.txt")


def write_to_position_log(message):
    with open(position_log_file, "a") as f:
        f.write("{} {}\n".format(datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), message))


def emit_calibration_positions():
    message = {
        "tip": printer3d.tiptilt.get_position("Tip"),
        "tilt": printer3d.tiptilt.get_position("Tilt"),
        "distance": printer3d.kdc.getCurrentPos(),
    }
    write_to_position_log(message)
    socketio.emit(
        "calibration_motor_move_complete",
        message,
        namespace="/calibrate",
        broadcast=True,
    )


# Create bluprint
blueprint = Blueprint(
    "manual_controls", __name__, url_prefix="/", static_folder="../static"
)

# Specify location of uploaded image and give default name
imagePath = os.path.join(
    CalibrationConfig.UPLOAD_FOLDER, "calibration_images", "temp.png"
)

# Decorator to handle navigation to calibration page
@blueprint.route("/calibrate")
def index():
    return render_template("manual_controls.html")


@socketio.on("set_external_control_enable", namespace="/calibrate")
def set_external_control_enable(message):
    """set_external_control -- Sets the variable determining if printer can be auto-calibrated"""
    external_control_enable.set_enable(message == "Enabled")


@socketio.on("get_external_control_enable", namespace="/calibrate")
def get_external_control_enable():
    """Return the external control enable flag."""
    socketio.emit(
        "external_control_enable",
        external_control_enable.get_enable(),
        namespace="/calibrate",
        broadcast=True,
    )


@socketio.on("galil_go_to_top", namespace="/calibrate")
def galil_go_to_top():
    """Move main Z stage to max position (up)."""
    galil.goToZmax()
    socketio.emit("galil_done", namespace="/calibrate", broadcast=True)


@socketio.on("galil_go_to_bottom", namespace="/calibrate")
def galil_go_to_bottom():
    """ Move main z stage to min position (down)."""
    galil.goToZmin()
    socketio.emit("galil_done", namespace="/calibrate", broadcast=True)


@socketio.on("galil_home", namespace="/calibrate")
def home():
    """ Home main z stage."""
    galil.home()
    socketio.emit("galil_done", namespace="/calibrate", broadcast=True)


@socketio.on("galil_move", namespace="/calibrate")
def galil_move(message):
    """Move the main Z stage. All units in mm."""
    mode = message["mode"]
    speed = float(message["speed"])
    distance = float(message["distance"])
    acceleration = float(message["acceleration"])
    if mode == "absolute":
        galil.absMove(mm=distance, speed=speed, acceleration=acceleration)
    elif mode == "relative":
        galil.relMove(mm=distance, speed=speed, acceleration=acceleration)
    socketio.emit("galil_done", namespace="/calibrate", broadcast=True)


@socketio.on("galil_start_jog", namespace="/calibrate")
def galil_startJog(message):
    """Start jogging the main Z stage."""
    speed = float(message["speed"])
    galil.startJog(speed=speed)
    # socketio.emit('galil_done', namespace='/calibrate', broadcast=True)


@socketio.on("galil_stop_jog", namespace="/calibrate")
def galil_stopJog():
    """Stop jogging the main Z stage"""
    galil.stopJog()
    socketio.emit("galil_done", namespace="/calibrate", broadcast=True)


@socketio.on("galil_get_position", namespace="/calibrate")
def galil_get_position():
    """Get the position the main Z stage."""
    message = {"position": galil.cntsToMm(galil.getPosition())}
    socketio.emit("galil_position", message, namespace="/calibrate", broadcast=True)


@socketio.on("calibration_motor_move", namespace="/calibrate")
def moveCalibrationMotor(message):
    axis = message["axis"]
    distance_um = float(message["microns"])
    mode = message["mode"]
    fast = message["fast"]
    mode = (
        mode != "absolute"
    )  # convert mode to True/False, absolute is true, all else is false
    if axis == "Distance":
        printer3d.kdc.move(distance_um, relative=mode)
    else:
        printer3d.tiptilt.move(axis, distance_um, relative=mode, fast=fast)
    emit_calibration_positions()


@socketio.on("calibration_motor_home", namespace="/calibrate")
def homeCalibrationMotor(message):
    axis = message["axis"]
    if axis == "Distance":
        printer3d.kdc.home()
    else:
        printer3d.tiptilt.home()
    emit_calibration_positions()


@socketio.on("light_engine_stop", namespace="/calibrate")
def lightEngineStop():
    """Turn off the LED in the light engin."""
    projector.stop_sequencer()
    socketio.emit("light_engine_stop_complete", namespace="/calibrate", broadcast=True)


@socketio.on("light_engine_start", namespace="/calibrate")
def lightEngineProject(message):
    """Project the image with the given settings."""
    ledPower = int(message["ledPower"])
    repeat = int(message["repeat"])
    exposure = int(message["exposure"])
    projector.project(imagePath, exposure, ledPower, repeat)
    socketio.emit("light_engine_start_complete", namespace="/calibrate", broadcast=True)


@blueprint.route("handle-calibration-upload", methods=["POST"])
def handleUpload():
    if "file" in request.files:  # Check if the post request has the file part
        file = request.files["file"]  # Get the file
        if file.filename != "" and file:  # File part of request actually has a file
            try:
                with Image.open(file) as img:  # Open file as PIL object
                    # Check imagePath format and mode
                    if img.format == "PNG" and img.mode == "L":
                        # Seek to the beginning of file (fixes bug in Werkzeug file I\O)
                        file.stream.seek(0)
                        file.save(imagePath)  # save it to the server
                        socketio.emit(
                            "calibration_image_uploaded",
                            namespace="/calibrate",
                            broadcast=True,
                        )
                        return ""
            except (OSError, FileNotFoundError):  # File has big issues
                pass
    socketio.emit("calibration_image_bad", namespace="/calibrate", broadcast=True)
    return ""
