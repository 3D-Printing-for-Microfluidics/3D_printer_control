import threading
import logging

from printer_server.hardware_configuration.hardware_configuration import driver_handles
from printer_server.extensions import socketio
from printer_server.threading_wrapper import Thread
import printer_server.views.manual_controls

tiptilt = driver_handles.tiptilt

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


@socketio.on("tiptilt_get_positions", namespace="/manual")
def get_tiptilt_positions(emit=True, log=False):
    last_positions = (
        printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
    )

    new_tip = tiptilt.get_position("tip")*1000
    new_tilt = tiptilt.get_position("tilt")*1000

    if new_tip is not None and new_tip == "undef":
        last_positions["tip"] = new_tip
        last_positions["tilt"] = new_tilt

    if log:
        printer_server.views.manual_controls.write_to_position_log(last_positions)

    if emit:
        socketio.emit(
            "tiptilt_done",
            last_positions,
            namespace="/manual"
        )

    return last_positions

@socketio.on("tiptilt_motor_move", namespace="/manual")
def moveTipTiltMotor(message):
    axis = message["axis"]
    distance_mrad = float(message["mrad"])
    mode = message["mode"]
    fast = message["fast"]
    mode = (
        mode != "absolute"
    )  # convert mode to True/False, absolute is true, all else is false
    tiptilt.move(axis, distance_mrad/1000, relative=mode, fast=fast)
    get_tiptilt_positions(log=message["log"])


@socketio.on("tiptilt_motor_home", namespace="/manual")
def homeTipTiltMotor():
    def func():
        tiptilt.home()
        get_tiptilt_positions(log=True)

    t = Thread(log, name="tiptilt_snip_home_thread", target=func)
    t.start()
