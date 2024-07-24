from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles

visitech = driver_handles.visitech


@socketio.on("visitech_stop", namespace="/manual")
def visitechStop():
    """Turn off the LED in the light engine."""
    visitech.stop_sequencer()
    socketio.emit("visitech_update_led_state", False, namespace="/manual")
    socketio.emit("visitech_done", namespace="/manual")


@socketio.on("visitech_start", namespace="/manual")
def visitechProject(message):
    """Project the image with the given settings."""
    ledPower = int(message["ledPower"])
    repeat = int(message["repeat"])
    exposure = int(message["exposure"])
    led = int(message.get("led", 0))
    socketio.emit("visitech_update_led_state", True, namespace="/manual")
    visitech.project(exposure, ledPower, repeat, led_num=led)
    if repeat != 0:
        socketio.emit("visitech_update_led_state", False, namespace="/manual")
    socketio.emit("visitech_done", namespace="/manual")


@socketio.on("visitech_get_status", namespace="/manual")
def visitechStatus():
    socketio.emit(
        "visitech_return_status",
        visitech.read_all_status(warn="ALL"),
        namespace="/manual"
    )


def getLedStatus():
    return visitech.led_on
