# -*- coding: utf-8 -*-
"""Control view."""
import os
import sys
import glob
import threading
import numpy as np
from pathlib import Path
from datetime import datetime
from PIL import Image
from flask import Blueprint, request, render_template

from printer_server.extensions import socketio
from printer_server.settings import Config
from printer_server.hardware_configuration import hardware_driver_handles
from printer_server.views.home import has_bad_metadata
from printer_server.views.home import clean_uploaded_file


class External_Control:
    def __init__(self):
        self.enable_flag = False

    def set_enable(self, status):
        self.enable_flag = status

    def get_enable(self):
        return self.enable_flag


galil = hardware_driver_handles.galil
projector = hardware_driver_handles.projector
tiptilt = hardware_driver_handles.tiptilt
kdc = hardware_driver_handles.kdc
external_control_enable = External_Control()
position_log_file = str(Path.cwd() / "logs" / "calibration_position_log.txt")


def write_to_position_log(message):
    with open(position_log_file, "a") as f:
        f.write("{} {}\n".format(datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), message))


@socketio.on("get_calibration_positions", namespace="/manual")
def get_calibration_positions():
    message = {
        "tip": tiptilt.get_position("Tip"),
        "tilt": tiptilt.get_position("Tilt"),
        "distance": kdc.getCurrentPos(),
    }
    socketio.emit(
        "calibration_positions", message, namespace="/manual", broadcast=True,
    )
    return message


def emit_calibration_positions():
    message = get_calibration_positions()
    write_to_position_log(message)
    socketio.emit(
        "calibration_motor_move_complete", message, namespace="/manual", broadcast=True,
    )


# Create bluprint
blueprint = Blueprint(
    "manual_controls", __name__, url_prefix="/", static_folder="../static"
)

# Specify location of uploaded image and give default name
imagePath = os.path.join(Config.UPLOAD_FOLDER, "calibration_images", "temp.png")
strobeImagePath = os.path.join(Config.UPLOAD_FOLDER, "calibration_images", "strobe.bmp")

# Decorator to handle navigation to calibration page
@blueprint.route("/manual")
def index():
    return render_template(
        "manual_controls.html",
        tip_position=tiptilt.get_position("Tip"),
        tilt_position=tiptilt.get_position("Tilt"),
        dist_position=kdc.getCurrentPos(),
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


@socketio.on("galil_go_to_top", namespace="/manual")
def galil_go_to_top():
    """Move main Z stage to max position (up)."""
    galil.goToZmax()
    socketio.emit("galil_done", namespace="/manual", broadcast=True)


@socketio.on("galil_go_to_bottom", namespace="/manual")
def galil_go_to_bottom():
    """ Move main z stage to min position (down)."""
    galil.goToZmin()
    socketio.emit("galil_done", namespace="/manual", broadcast=True)


@socketio.on("galil_home", namespace="/manual")
def home():
    """ Home main z stage."""
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
        kdc.move(distance_um, relative=mode)
    else:
        tiptilt.move(axis, distance_um, relative=mode, fast=fast)
    emit_calibration_positions()


@socketio.on("calibration_motor_home", namespace="/manual")
def homeCalibrationMotor(message):
    axis = message["axis"]

    def func(axis):
        if axis == "Distance":
            kdc.home()
        else:
            tiptilt.home()
        emit_calibration_positions()

    t = threading.Thread(target=func, args=[axis])
    t.start()


@socketio.on("light_engine_stop", namespace="/manual")
def lightEngineStop():
    """Turn off the LED in the light engin."""
    projector.stop_sequencer()
    socketio.emit("light_engine_stop_complete", namespace="/manual", broadcast=True)


@socketio.on("light_engine_start", namespace="/manual")
def lightEngineProject(message):
    """Project the image with the given settings."""
    ledPower = int(message["ledPower"])
    repeat = int(message["repeat"])
    exposure = int(message["exposure"])
    projector.project(imagePath, exposure, ledPower, repeat)
    socketio.emit("light_engine_start_complete", namespace="/manual", broadcast=True)


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
    
@socketio.on("light_engine_enable_strobe", namespace="/manual")
def enableStrobe():
    projector.enable_strobe()
    socketio.emit(
        "strobe_enabled",
        namespace="/manual",
        broadcast=True,
    )

@socketio.on("light_engine_disable_strobe", namespace="/manual")
def disableStrobe():
    projector.disable_strobe()
    socketio.emit(
        "strobe_disabled",
        namespace="/manual",
        broadcast=True,
    )
    
@socketio.on("light_engine_strobe", namespace="/manual")
def lightEngineProjectStrobe(message):
    """Project the image with the given settings."""
    ledPower = int(message["ledPower"])
    exposure = int(message["exposure"])
    index = int(message["index"])
    projector.project_strobe(exposure, ledPower, index = index)
    socketio.emit("light_engine_strobe_complete", namespace="/manual", broadcast=True)

def strobe_pack_images(is_calibration, strobe_folder):
    resolution = (3, 2560, 1600)
    index = 0
    image = 0
    channel = 0
    bit = 0

    # get all pngs in folder
    files = sorted(glob.glob(strobe_folder + "/*.png"))
    num_images = len(files)//24 + 1

    # create blank bmps
    bmp_imgs = []
    for i in range(num_images):
        bmp_imgs.append(np.zeros(resolution[::-1], dtype="uint8"))

    # pack pngs in bmps
    for filepath in files:
        try:
            with Image.open(filepath) as input_img:
                if input_img.format == "PNG" and input_img.mode == "L":
                    masked_input_array = np.bitwise_and(np.array(input_img), 1<<bit)
                    bmp_imgs[image][:, :, channel] = np.bitwise_or(bmp_imgs[image][:, :, channel], masked_input_array)
                    
                    index = index + 1
                    image = index//24
                    channel = (index%24)//8
                    bit = index%8
        except (OSError, FileNotFoundError):
            Pass
        
    # save bmps
    for i in range(num_images):
        log.info("Packing image {}".format(i))
        file_name = strobe_folder + "/{}.bmp".format(i)
        Image.fromarray(bmp_imgs[i], "RGB").save(file_name)

def strobe_upload_images(is_calibration, strobe_folder):
    """Uploads all BMPs in given folder to projector.
    If is_calibration, only one BMP is uploaded to index 0
    Otherwise, the images are uploaded starting at index 1."""

    files = sorted(glob.glob(strobe_folder + "/*.bmp"))
    num_images = len(files)

    if is_calibration and num_images > 1:
        log.warning("Too many calibration images to pack in single BMP!")

    # save bmps
    count = 1
    for file_name in files:
        with open(file_name, mode='rb') as file:
            file_content = file.read()
            file_size = len(file_content)
            if (is_calibration == 'True'):
                projector.upload_image(0, file_size, file_content)
                return
            else:
                projector.upload_image(i, file_size, file_content)
                count = count + 1

    
@blueprint.route("handle-calibration-upload-strobe", methods=["POST"])
def handleUploadStrobe(message):
    is_calibration = message["is_calibration"]
    for _, f in enumerate(request.files.getlist("file")):
        strobe_folder = None
        if (is_calibration == 'True'):
            strobe_folder = Path(Config.UPLOAD_FOLDER) / Path("calibration_images/defaults")
        else:
            strobe_folder = Path(Config.UPLOAD_FOLDER) / Path("calibration_images/uploads")
        zip_file = os.path.join(
            Config.UPLOAD_FOLDER,
            "calibration_images",
            "temp.zip",
        )
        f.save(zip_file)
        if has_bad_metadata(zip_file):
            log.debug("Removing hiden '__MACOSX' folder from %s ...", f.filename)
            clean_uploaded_file(zip_file)
        # clear any old contents from the calibration_images folder
        try:
            shutil.rmtree(strobe_folder)
        except FileNotFoundError:
            pass

        # extract to current_job
        with ZipFile(zip_file, "r") as f:
            f.extractall(strobe_folder)
        os.remove(zip_file)

        # pack and upload to visitech
        strobe_pack_images(is_calibration, strobe_folder)
        strobe_upload_images(is_calibration, strobe_folder)

        log.info("Strobe set %s uploaded successfully.", f.filename)
        socketio.emit(
            "calibration_image_uploaded_strobe",
            namespace="/manual",
            broadcast=True,
        )
    socketio.emit("calibration_image_bad_strobe", namespace="/manual", broadcast=True)
    return ""