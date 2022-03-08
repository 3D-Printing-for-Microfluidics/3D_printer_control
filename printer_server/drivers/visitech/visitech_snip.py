import os
from printer_server.settings import Config
from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles

visitech = driver_handles.visitech

# Specify location of uploaded image and give default name
imagePath = os.path.join(Config.UPLOAD_FOLDER, "calibration_images", "temp.png")


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
