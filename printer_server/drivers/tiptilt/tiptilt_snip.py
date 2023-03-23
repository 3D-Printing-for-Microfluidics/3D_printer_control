import threading

from printer_server.hardware_configuration import driver_handles
from printer_server.extensions import socketio
import printer_server.views.manual_controls

tiptilt = driver_handles.tiptilt


def get_tiptilt_positions():
    last_positions = (
        printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
    )

    new_tip = tiptilt.get_position("tip")
    new_tilt = tiptilt.get_position("tilt")

    if new_tip is not None and new_tip is not "undef":
        last_positions["tip"] = new_tip
        last_positions["tilt"] = new_tilt

    return last_positions


@socketio.on("get_tiptilt_positions", namespace="/manual")
def get_tiptilt_positions_socket():
    message = get_tiptilt_positions()
    socketio.emit(
        "calibration_tiptilt_positions",
        message,
        namespace="/manual",
        broadcast=True,
    )
    return message


def emit_tiptilt_positions(log=False):
    message = get_tiptilt_positions()

    if log:
        printer_server.views.manual_controls.write_to_position_log(message)
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
def homeTipTiltMotor():
    def func():
        tiptilt.home()
        emit_tiptilt_positions(log=True)

    t = threading.Thread(target=func)
    t.start()
