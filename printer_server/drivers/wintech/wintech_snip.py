from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles

wintech = driver_handles.wintech


@socketio.on("wintech_stop", namespace="/manual")
def wintechStop():
    """Turn off the LED in the light engine."""
    wintech.stop_sequencer()
    socketio.emit("update_wintech_led_status", False, namespace="/manual")
    socketio.emit("wintech_stop_complete", namespace="/manual")


@socketio.on("wintech_start", namespace="/manual")
def wintechProject(message):
    """Project the image with the given settings."""
    ledPower = int(message["ledPower"])
    repeat = int(message["repeat"])
    exposure = int(message["exposure"])
    socketio.emit("update_wintech_led_status", True, namespace="/manual")
    wintech.project(exposure, ledPower, repeat)
    if repeat != 0:
        socketio.emit("update_wintech_led_status", False, namespace="/manual")
    socketio.emit("wintech_start_complete", namespace="/manual")


# @socketio.on("wintech_get_status", namespace="/manual")
# def wintechStatus():
#     socketio.emit(
#         "wintech_status",
#         wintech.read_all_status(),
#         namespace="/manual"
#     )


def getLedStatus():
    return wintech.led_on
