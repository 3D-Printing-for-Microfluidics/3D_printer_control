import os
import logging
from printer_server.settings import Config
from printer_server.extensions import socketio
from flask import request, Blueprint, render_template
from printer_server.hardware_configuration.hardware_configuration import driver_handles

from PIL import Image

screen = driver_handles.screen

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def handleUpload(request):
    try:
        if "file" in request.files:  # Check if the post request has the file part
            file = request.files["file"]  # Get the file
            light_engine = request.form["light_engine"]
            # Specify location of uploaded image and give default name
            imagePath = os.path.join(
                Config.UPLOAD_FOLDER, "calibration_images", f"{light_engine}.png"
            )
            if file.filename != "" and file:  # File part of request actually has a file
                try:
                    with Image.open(file) as img:  # Open file as PIL object
                        # Check imagePath format and mode
                        if img.format == "PNG" and img.mode == "L":
                            # Seek to the beginning of file (fixes bug in Werkzeug file I\O)
                            file.stream.seek(0)
                            file.save(imagePath)  # save it to the server
                            socketio.emit(
                                "screen_image_uploaded",
                                light_engine,
                                namespace="/manual"
                            )
                            return ""
                except (OSError, FileNotFoundError):  # File has big issues
                    pass
        socketio.emit(
            "screen_image_bad", light_engine, namespace="/manual"
        )
        return ""
    except Exception as ex:
        log.warn("Screen manual control failed (%s)", ex)
        socketio.emit("hardware_failure", "screen", namespace="/manual")


def fetch_previews():
    try:
        previews = {}
        for light_engine in screen.light_engines:
            screen_num = screen.getScreenNumber(light_engine)
            previews[light_engine] = screen.fetch_preview(screen_num)
        socketio.emit(
            "screen_previews", previews, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Screen manual control failed (%s)", ex)
        socketio.emit("hardware_failure", "screen", namespace="/manual")


@socketio.on("screen_draw", namespace="/manual")
def screenDraw(message):
    try:
        light_engine = message["light_engine"]
        imagePath = os.path.join(
            Config.UPLOAD_FOLDER, "calibration_images", f"{light_engine}.png"
        )
        screen_num = screen.getScreenNumber(light_engine)
        screen.draw(imagePath, screen=screen_num)
        socketio.emit(
            "screen_done", {light_engine: screen.fetch_preview(screen_num)}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Screen manual control failed (%s)", ex)
        socketio.emit("hardware_failure", "screen", namespace="/manual")


@socketio.on("screen_white", namespace="/manual")
def screenWhite(message):
    try:
        light_engine = message["light_engine"]
        imagePath = os.path.join(
            Config.PRINT_SERVER_FOLDER, f"drivers/{light_engine}/images", f"white.png"
        )
        screen_num = screen.getScreenNumber(light_engine)
        screen.draw(imagePath, screen=screen_num)
        socketio.emit(
            "screen_done", {light_engine: screen.fetch_preview(screen_num)}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Screen manual control failed (%s)", ex)
        socketio.emit("hardware_failure", "screen", namespace="/manual")


@socketio.on("screen_clear", namespace="/manual")
def screenClear(message):
    try:
        light_engine = message["light_engine"]
        screen_num = screen.getScreenNumber(light_engine)
        screen.clear(screen=screen_num)
        socketio.emit(
            "screen_done", {light_engine: screen.fetch_preview(screen_num)}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Screen manual control failed (%s)", ex)
        socketio.emit("hardware_failure", "screen", namespace="/manual")
