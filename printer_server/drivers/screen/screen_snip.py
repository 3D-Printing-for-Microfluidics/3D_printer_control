import os
import logging
from printer_server.settings import Config
from printer_server.extensions import socketio
from flask import request, Blueprint, render_template
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict

from PIL import Image

screen = driver_handles.screen
light_engines = driver_handles.light_engines

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
        log.warn("Screen manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "screen", namespace="/manual")

def screenLoad():
    try:
        data = {}
        for light_engine in screen.light_engines:
            light_corrected = screen.getLightCorrectionEnable(light_engine)
            dark_corrected = screen.getDarkCorrectionEnable(light_engine)
            data[light_engine] = {
                "light": light_corrected, 
                "dark": dark_corrected
            }
        socketio.emit(
            "screen_load", data, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Screen manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "screen", namespace="/manual")


def screenFetchPreviews():
    try:
        previews = {}
        for light_engine in screen.light_engines:
            previews[light_engine] = screen.fetch_preview(light_engine)
        socketio.emit(
            "screen_previews", previews, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Screen manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "screen", namespace="/manual")


@socketio.on("screen_light_grayscale_correction", namespace="/manual")
def screenLightGrayscaleCorrection(message):
    try:
        light_engine = message["light_engine"]
        correction = bool(message["correction"])
        screen.setCorrectionEnable(correction, screen.getDarkCorrectionEnable(light_engine), light_engine=light_engine)
        socketio.emit(
            "screen_done", {light_engine: screen.fetch_preview(light_engine)}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Screen manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "screen", namespace="/manual")

@socketio.on("screen_dark_grayscale_correction", namespace="/manual")
def screenDarkGrayscaleCorrection(message):
    try:
        light_engine = message["light_engine"]
        correction = bool(message["correction"])
        
        screen.setCorrectionEnable(screen.getLightCorrectionEnable(light_engine), correction, light_engine=light_engine)
        socketio.emit(
            "screen_done", {light_engine: screen.fetch_preview(light_engine)}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Screen manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "screen", namespace="/manual")

@socketio.on("screen_draw", namespace="/manual")
def screenDraw(message):
    try:
        light_engine = message["light_engine"]
        led_num = light_engines[light_engine].getCurrentLed()
        imagePath = os.path.join(
            Config.UPLOAD_FOLDER, "calibration_images", f"{light_engine}.png"
        )
        screen.draw(imagePath, light_engine=light_engine, led_num=led_num)
        socketio.emit(
            "screen_done", {light_engine: screen.fetch_preview(light_engine)}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Screen manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "screen", namespace="/manual")


@socketio.on("screen_white", namespace="/manual")
def screenWhite(message):
    try:
        light_engine = message["light_engine"]
        led_num = light_engines[light_engine].getCurrentLed()
        imagePath = os.path.join(
            Config.PRINT_SERVER_FOLDER, f"drivers/{light_engine}/images", f"white.png"
        )
        screen.draw(imagePath, light_engine=light_engine, led_num=led_num)
        socketio.emit(
            "screen_done", {light_engine: screen.fetch_preview(light_engine)}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Screen manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "screen", namespace="/manual")


@socketio.on("screen_clear", namespace="/manual")
def screenClear(message):
    try:
        light_engine = message["light_engine"]
        screen.clear(light_engine)
        socketio.emit(
            "screen_done", {light_engine: screen.fetch_preview(light_engine)}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Screen manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "screen", namespace="/manual")
