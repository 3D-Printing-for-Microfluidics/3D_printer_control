import os
import logging
from PIL import Image

from printer_server.settings import Config
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict
from printer_server.views.users import socket_require_permissions

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
                                "light_engine_image_uploaded",
                                light_engine,
                                namespace="/manual"
                            )
                            return ""
                except (OSError, FileNotFoundError):  # File has big issues
                    pass
        socketio.emit(
            "light_engine_image_bad", light_engine, namespace="/manual"
        )
        return ""
    except Exception as ex:
        log.warn("Light engine manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", light_engine, namespace="/manual")


def getGrayscaleCorrection():
    data = {}
    for light_engine in config_dict["light_engines"]:
        try:
            corrected = light_engines[light_engine].is_grayscale_corrected()
        except Exception as ex:
            log.warning("Light engine manual control failed (%s)", ex, exc_info=True)
            socketio.emit("hardware_failure", light_engine, namespace="/manual")
        data[light_engine] = corrected
    socketio.emit(
        "light_engine_load", data, namespace="/manual"
    )


def fetchPreviews():
        previews = {}
        for light_engine in config_dict["light_engines"]:
            try:
                previews[light_engine] = light_engines[light_engine].get_image_preview()
            except Exception as ex:
                log.warning("Light engine manual control failed (%s)", ex, exc_info=True)
                socketio.emit("hardware_failure", light_engine, namespace="/manual")
        socketio.emit(
            "light_engine_previews", previews, namespace="/manual"
        )
    

@socketio.on("light_engine_grayscale_correction", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def lightEngineGrayscaleCorrection(message):
    light_engine = message["light_engine"]
    try:
        correction = bool(message["correction"])
        led_num = int(message.get("led", 0))
        imagePath = light_engines[light_engine].get_image()
        if imagePath is not None:
            light_engines[light_engine].set_image(imagePath, led_num=led_num, grayscale_corrected=correction)
        socketio.emit(
            "light_engine_done", {light_engine: light_engines[light_engine].get_image_preview()}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Light engine manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", light_engine, namespace="/manual")


@socketio.on("light_engine_led_changed", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def lightEngineLEDChanged(message):
    light_engine = message["light_engine"]
    try:
        correction = bool(message["correction"])
        led_num = int(message.get("led", 0))
        imagePath = light_engines[light_engine].get_image()
        if imagePath is not None:
            light_engines[light_engine].set_image(imagePath, led_num=led_num, grayscale_corrected=correction)
        socketio.emit(
            "light_engine_done", {light_engine: light_engines[light_engine].get_image_preview()}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Light engine manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", light_engine, namespace="/manual")


@socketio.on("light_engine_draw_image", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def lightEngineDraw(message):
    light_engine = message["light_engine"]
    try:
        correction = bool(message["correction"])
        led_num = int(message.get("led", 0))
        imagePath = os.path.join(
            Config.UPLOAD_FOLDER, "calibration_images", f"{light_engine}.png"
        )
        light_engines[light_engine].set_image(imagePath, led_num=led_num, grayscale_corrected=correction)
        socketio.emit(
            "light_engine_done", {light_engine: light_engines[light_engine].get_image_preview()}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Light engine manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", light_engine, namespace="/manual")


@socketio.on("light_engine_draw_white", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def lightEngineWhite(message):
    light_engine = message["light_engine"]
    try:
        correction = bool(message["correction"])
        led_num = int(message.get("led", 0))
        imagePath = os.path.join(
            Config.PRINT_SERVER_FOLDER, f"drivers/{light_engine}/images", f"white.png"
        )
        light_engines[light_engine].set_image(imagePath, led_num=led_num, grayscale_corrected=correction)
        socketio.emit(
            "light_engine_done", {light_engine: light_engines[light_engine].get_image_preview()}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Light engine manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", light_engine, namespace="/manual")


@socketio.on("light_engine_draw_black", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def lightEngineClear(message):
    light_engine = message["light_engine"]
    try:
        correction = bool(message["correction"])
        led_num = int(message.get("led", 0))
        imagePath = os.path.join(
            Config.PRINT_SERVER_FOLDER, f"drivers/{light_engine}/images", f"black.png"
        )
        light_engines[light_engine].set_image(imagePath, led_num=led_num, grayscale_corrected=correction)
        socketio.emit(
            "light_engine_done", {light_engine: light_engines[light_engine].get_image_preview()}, namespace="/manual"
        )
    except Exception as ex:
        log.warn("Light engine manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", light_engine, namespace="/manual")


@socketio.on("light_engine_stop", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def light_engine_stop(light_engine):
    """Turn off the LED in the light engine."""
    try:
        light_engines[light_engine].stop_sequencer()
        light_engines[light_engine].idle_on()
        socketio.emit("light_engine_update_led_state", {"light_engine":light_engine, "state":False}, namespace="/manual")
        socketio.emit("light_engine_done", namespace="/manual")
    except Exception as ex:
        log.warn("%s manual control failed (%s)", light_engine.capitalize(), ex, exc_info=True)
        socketio.emit("hardware_failure", light_engine, namespace="/manual")


@socketio.on("light_engine_start", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def light_engine_start(message):
    """Project the image with the given settings."""
    try:
        light_engine = message["light_engine"]
        ledPower = int(message["ledPower"])
        repeat = int(message["repeat"])
        exposure = int(message["exposure"])
        led = int(message.get("led", 0))
        correction = int(message.get("correction", 0))
        socketio.emit("light_engine_update_led_state", {"light_engine":light_engine, "state":True}, namespace="/manual")
        light_engines[light_engine].idle_off()

        light_engines[light_engine].stop_sequencer()
        light_engines[light_engine].setup_exposure(exposure, led_power=ledPower, repeat=repeat, led_num=led)
        light_engines[light_engine].perform_exposure()
        if repeat != 0:
            socketio.emit("light_engine_update_led_state", {"light_engine":light_engine, "state":False}, namespace="/manual")
            light_engines[light_engine].idle_on()
        socketio.emit("light_engine_done", namespace="/manual")
    except Exception as ex:
        log.warn("%s manual control failed (%s)", light_engine.capitalize(), ex, exc_info=True)
        socketio.emit("hardware_failure", light_engine, namespace="/manual")


@socketio.on("light_engine_get_status", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def light_engine_get_status(light_engine):
    try:
        socketio.emit(
            "light_engine_return_status",
            light_engines[light_engine].read_all_status(warn="ALL"),
            namespace="/manual"
        )
    except Exception as ex:
        log.warn("%s manual control failed (%s)", light_engine.capitalize(), ex, exc_info=True)
        socketio.emit("hardware_failure", light_engine, namespace="/manual")


def getLedStatus(emit=True):
    for light_engine in config_dict["light_engines"]:
        try:
            state = light_engines[light_engine].get_led_status()
            if emit:
                socketio.emit(f"light_engine_update_led_state", {"light_engine": light_engine, "state":state}, namespace="/manual")
        except Exception as ex:
            log.warn("%s manual control failed (%s)", light_engine.capitalize(), ex, exc_info=True)
            socketio.emit("hardware_failure", light_engine, namespace="/manual")

