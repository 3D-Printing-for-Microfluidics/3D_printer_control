import threading

from printer_server.hardware_configuration import driver_handles
from printer_server.extensions import socketio
import printer_server.views.manual_controls

kdc = driver_handles.kdc


def get_kdc_positions():
    last_positions = printer_server.views.manual_controls.get_last_calibration_positions()
    message = {
        "tip": last_positions["tip"],
        "tilt": last_positions["tilt"],
        "distance": kdc.getCurrentPos(),
    }

    return message


@socketio.on("get_kdc_positions", namespace="/manual")
def get_kdc_positions_socket():
    message = get_kdc_positions()
    socketio.emit(
        "calibration_positions",
        message,
        namespace="/manual",
        broadcast=True,
    )
    return message


def emit_kdc_positions(log=False):
    message = get_kdc_positions()

    if log:
        printer_server.views.manual_controls.write_to_position_log(message)
    socketio.emit(
        "kdc_motor_move_complete",
        message,
        namespace="/manual",
        broadcast=True,
    )


@socketio.on("kdc_motor_move", namespace="/manual")
def moveKDCMotor(message):
    distance_um = float(message["microns"])
    mode = message["mode"]
    mode = (
        mode != "absolute"
    )  # convert mode to True/False, absolute is true, all else is false
    kdc.move(distance_um, relative=mode)
    emit_kdc_positions(log=message["log"])


@socketio.on("kdc_motor_home", namespace="/manual")
def homeKDCMotor(message):
    axis = message["axis"]

    def func(axis):
        kdc.home()
        emit_kdc_positions(log=True)

    t = threading.Thread(target=func, args=[axis])
    t.start()
