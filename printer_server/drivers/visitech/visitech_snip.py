from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles

visitech = driver_handles.visitech


@socketio.on("visitech_stop", namespace="/manual")
def visitechStop():
    """Turn off the LED in the light engine."""
    visitech.stop_sequencer()
    socketio.emit("update_led_status", False, namespace="/manual")
    socketio.emit("visitech_stop_complete", namespace="/manual", broadcast=True)


@socketio.on("visitech_start", namespace="/manual")
def visitechProject(message):
    """Project the image with the given settings."""
    ledPower = int(message["ledPower"])
    repeat = int(message["repeat"])
    exposure = int(message["exposure"])
    socketio.emit("update_led_status", True, namespace="/manual")
    visitech.project(exposure, ledPower, repeat)
    if repeat != 0:
        socketio.emit("update_led_status", False, namespace="/manual")
    socketio.emit("visitech_start_complete", namespace="/manual", broadcast=True)


@socketio.on("visitech_get_status", namespace="/manual")
def visitechStatus():
    socketio.emit(
        "visitech_status",
        visitech.read_all_status(),
        namespace="/manual",
        broadcast=True,
    )
