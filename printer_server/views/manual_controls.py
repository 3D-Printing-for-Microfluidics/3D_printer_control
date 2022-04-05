# -*- coding: utf-8 -*-
"""Control view."""
import os
from printer_server.drivers import wintech
import threading
from pathlib import Path
from datetime import datetime
from PIL import Image
from flask import Blueprint, request, render_template

from printer_server.extensions import socketio
from printer_server.settings import Config
from printer_server.hardware_configuration import driver_handles


class External_Control:
    def __init__(self):
        self.enable_flag = False

    def set_enable(self, status):
        self.enable_flag = status

    def get_enable(self):
        return self.enable_flag


galil = driver_handles.galil
visitech = driver_handles.visitech
wintech = driver_handles.wintech
tiptilt = driver_handles.tiptilt
external_control_enable = External_Control()
position_log_file = str(Path.cwd() / "logs" / "calibration_position_log.txt")


def write_to_position_log(message):
    with open(position_log_file, "a") as f:
        f.write("{} {}\n".format(datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), message))


def get_calibration_positions():
    message = {
        "tip": tiptilt.get_position("Tip"),
        "tilt": tiptilt.get_position("Tilt"),
        "distance": int(galil.cntsToMm(galil.getPosition(axis="Z"), axis="Z") * 1000),
    }

    if message["tip"] is "undef":
        last_positions = get_last_calibration_positions()
        message["tip"] = last_positions[0]
        message["tilt"] = last_positions[1]

    return message


@socketio.on("get_calibration_positions", namespace="/manual")
def get_calibration_positions_socket():
    message = get_calibration_positions()
    socketio.emit(
        "calibration_positions",
        message,
        namespace="/manual",
        broadcast=True,
    )
    return message


def emit_calibration_positions(log=False):
    message = get_calibration_positions()

    if log:
        write_to_position_log(message)
    socketio.emit(
        "calibration_motor_move_complete",
        message,
        namespace="/manual",
        broadcast=True,
    )


# Create bluprint
blueprint = Blueprint(
    "manual_controls", __name__, url_prefix="/", static_folder="../static"
)

# Specify location of uploaded image and give default name
imagePath = os.path.join(Config.UPLOAD_FOLDER, "calibration_images", "temp.png")
imagePathWintech = os.path.join(
    Config.UPLOAD_FOLDER, "calibration_images", "tempWintech.png"
)


def get_last_calibration_positions():
    """Return the last focused position for the distance axis from the
    position log file.
    """
    log_file = Path(Config.PROJECT_ROOT) / "logs" / "calibration_position_log.txt"
    last_line = None
    with open(log_file) as f:
        for line in f:
            last_line = line.rstrip()
    for char in ["{", "}", ":", "'", ","]:
        last_line = last_line.replace(char, "")
    return [
        float(last_line.split(" ")[-5]),
        float(last_line.split(" ")[-3]),
        float(last_line.split(" ")[-1]),
    ]


# Decorator to handle navigation to calibration page
@blueprint.route("/manual")
def index():
    positions = get_last_calibration_positions()
    return render_template(
        "manual_controls.html",
        tip_position=positions[0],
        tilt_position=positions[1],
        dist_position=positions[2],
        hostname=Config.HOSTNAME,
    )


@socketio.on("set_external_control_enable", namespace="/manual")
def set_external_control_enable(message):
    """set_external_control -- Sets the variable determining if printer can be auto-calibrated"""
    external_control_enable.set_enable(message == "Enabled")


@socketio.on("get_external_control_enable", namespace="/manual")
def get_external_control_enable():
    """Return the external control enable flag."""
    socketio.emit(
        "external_control_enable",
        external_control_enable.get_enable(),
        namespace="/manual",
        broadcast=True,
    )


@socketio.on("galil_go_to_calibration", namespace="/manual")
def galil_go_to_calibration():
    """Move main Z stage to default position with calibration system."""
    galil.goToZcalibration()
    socketio.emit("galil_done", namespace="/manual", broadcast=True)


@socketio.on("galil_go_to_top", namespace="/manual")
def galil_go_to_top():
    """Move main Z stage to max position (up)."""
    galil.goToZmax()
    socketio.emit("galil_done", namespace="/manual", broadcast=True)


@socketio.on("galil_go_to_bottom", namespace="/manual")
def galil_go_to_bottom():
    """Move main z stage to min position (down)."""
    galil.goToZmin()
    socketio.emit("galil_done", namespace="/manual", broadcast=True)


@socketio.on("galil_home", namespace="/manual")
def home():
    """Home main z stage."""
    galil.home()
    socketio.emit("galil_done", namespace="/manual", broadcast=True)


@socketio.on("galil_move", namespace="/manual")
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
    socketio.emit("galil_done", namespace="/manual", broadcast=True)


@socketio.on("galil_start_jog", namespace="/manual")
def galil_startJog(message):
    """Start jogging the main Z stage."""
    speed = float(message["speed"])
    galil.startJog(speed=speed)
    # socketio.emit('galil_done', namespace='/manual', broadcast=True)


@socketio.on("galil_stop_jog", namespace="/manual")
def galil_stopJog():
    """Stop jogging the main Z stage"""
    galil.stopJog()
    socketio.emit("galil_done", namespace="/manual", broadcast=True)


@socketio.on("galil_get_position", namespace="/manual")
def galil_get_position():
    """Get the position the main Z stage."""
    message = {"position": galil.cntsToMm(galil.getPosition())}
    socketio.emit("galil_position", message, namespace="/manual", broadcast=True)


@socketio.on("calibration_motor_move", namespace="/manual")
def moveCalibrationMotor(message):
    axis = message["axis"]
    distance_um = float(message["microns"])
    mode = message["mode"]
    fast = message["fast"]
    mode = (
        mode != "absolute"
    )  # convert mode to True/False, absolute is true, all else is false
    if axis == "Distance":
        if not mode:
            galil.absMove(mm=distance_um / 1000, speed=25, axis="Z")
        else:
            galil.relMove(mm=distance_um / 1000, speed=25, axis="Z")
    else:
        tiptilt.move(axis, distance_um, relative=mode, fast=fast)
    emit_calibration_positions(log=message["log"])


@socketio.on("calibration_motor_home", namespace="/manual")
def homeCalibrationMotor(message):
    axis = message["axis"]

    def func(axis):
        if axis == "Distance":
            pass
        else:
            tiptilt.home()
        emit_calibration_positions(log=True)

    t = threading.Thread(target=func, args=[axis])
    t.start()


@socketio.on("light_engine_stop", namespace="/manual")
def lightEngineStop():
    """Turn off the LED in the light engin."""
    visitech.stop_sequencer()
    socketio.emit("light_engine_stop_complete", namespace="/manual", broadcast=True)


@socketio.on("light_engine_start", namespace="/manual")
def lightEngineProject(message):
    """Project the image with the given settings."""
    ledPower = int(message["ledPower"])
    repeat = int(message["repeat"])
    exposure = int(message["exposure"])
    driver_handles.screen.draw(imagePath)
    visitech.project(exposure, ledPower, repeat)
    socketio.emit("light_engine_start_complete", namespace="/manual", broadcast=True)


@socketio.on("light_engine_get_status", namespace="/manual")
def lightEngineStatus():
    socketio.emit(
        "light_engine_status",
        visitech.read_all_status(),
        namespace="/manual",
        broadcast=True,
    )


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
                            namespace="/manual",
                            broadcast=True,
                        )
                        return ""
            except (OSError, FileNotFoundError):  # File has big issues
                pass
    socketio.emit("calibration_image_bad", namespace="/manual", broadcast=True)
    return ""


@socketio.on("light_engine_stop_wintech", namespace="/manual")
def lightEngineStopWintech():
    """Turn off the LED in the light engin."""
    print("stop wintech")
    wintech.stop()
    socketio.emit(
        "light_engine_stop_complete_wintech", namespace="/manual", broadcast=True
    )


@socketio.on("light_engine_start_wintech", namespace="/manual")
def lightEngineProjectWintech(message):
    """Project the image with the given settings."""
    print("start wintech")
    ledPower = int(message["ledPower"])
    repeat = int(message["repeat"])
    exposure = int(message["exposure"])
    driver_handles.screen.draw(imagePathWintech, 1)
    wintech.project(exposure, repeat, ledPower)
    socketio.emit(
        "light_engine_start_complete_wintech", namespace="/manual", broadcast=True
    )


@blueprint.route("handle-calibration-upload-wintech", methods=["POST"])
def handleUploadWintech():
    print("upload wintech")
    if "file" in request.files:  # Check if the post request has the file part
        file = request.files["file"]  # Get the file
        if file.filename != "" and file:  # File part of request actually has a file
            try:
                with Image.open(file) as img:  # Open file as PIL object
                    # Check imagePath format and mode
                    if img.format == "PNG" and img.mode == "L":
                        # Seek to the beginning of file (fixes bug in Werkzeug file I\O)
                        file.stream.seek(0)
                        file.save(imagePathWintech)  # save it to the server
                        socketio.emit(
                            "calibration_image_uploaded_wintech",
                            namespace="/manual",
                            broadcast=True,
                        )
                        return ""
            except (OSError, FileNotFoundError):  # File has big issues
                pass
    socketio.emit("calibration_image_bad_wintech", namespace="/manual", broadcast=True)
    return ""
