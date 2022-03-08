import threading

from printer_server.hardware_configuration import driver_handles
from printer_server.extensions import socketio
from printer_server.views.manual_controls import (
    get_last_calibration_positions,
    write_to_position_log,
)

tiptilt = driver_handles.tiptilt


def get_tiptilt_positions():
    last_positions = get_last_calibration_positions()
    message = {
        "tip": tiptilt.get_position("Tip"),
        "tilt": tiptilt.get_position("Tilt"),
        "distance": last_positions[2],
    }

    if message["tip"] is None or message["tip"] is "undef":
        message["tip"] = last_positions[0]
        message["tilt"] = last_positions[1]

    return message


@socketio.on("get_tiptilt_positions", namespace="/manual")
def get_tiptilt_positions_socket():
    message = get_tiptilt_positions()
    socketio.emit(
        "calibration_positions",
        message,
        namespace="/manual",
        broadcast=True,
    )
    return message


def emit_tiptilt_positions(log=False):
    message = get_tiptilt_positions()

    if log:
        write_to_position_log(message)
    socketio.emit(
        "tiptilt_motor_move_complete",
        message,
        namespace="/manual",
        broadcast=True,
    )


@socketio.on("tiptilt_motor_move", namespace="/manual")
def moveTipTiltMotor(message):
    axis = message["axis"]
    distance_um = float(message["microns"])
    mode = message["mode"]
    fast = message["fast"]
    mode = (
        mode != "absolute"
    )  # convert mode to True/False, absolute is true, all else is false
    tiptilt.move(axis, distance_um, relative=mode, fast=fast)
    emit_tiptilt_positions(log=message["log"])


@socketio.on("tiptilt_motor_home", namespace="/manual")
def homeTipTiltMotor(message):
    axis = message["axis"]

    def func(axis):
        tiptilt.home()
        emit_tiptilt_positions(log=True)

    t = threading.Thread(target=func, args=[axis])
    t.start()
