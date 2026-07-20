import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import (
    driver_handles,
    config_dict,
)
from printer_server.views.users import socket_require_permissions
import printer_server.views.manual_controls

import time

bp_stage = driver_handles.bp_stage

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

start_time = 0
stop_time = 0


@socketio.on("bp_go_to_top", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def bp_go_to_top():
    """Move main Z stage to max position (up)."""
    try:
        global start_time, stop_time
        start_time = time.time()
        bp_stage.goToBPtop()
        stop_time = time.time()
        socketio.emit("bp_done", bp_get_position(notify=False), namespace="/manual")
    except Exception as ex:
        log.warn("BP stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "bp", namespace="/manual")


@socketio.on("bp_home", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def bp_home():
    """Home main z stage."""
    try:
        global start_time, stop_time
        start_time = time.time()
        bp_stage.home()
        stop_time = time.time()
        socketio.emit("bp_done", bp_get_position(notify=False), namespace="/manual")
    except Exception as ex:
        log.warn("BP stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "bp", namespace="/manual")


@socketio.on("bp_move", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def bp_move(message):
    """Move the main Z stage in um."""
    try:
        global start_time, stop_time
        mode = message["mode"]
        distance = float(message["distance"]) / 1000
        speed = message.get("speed", bp_stage.getDefaultBPSpeed())
        acceleration = message.get("acceleration", bp_stage.getDefaultBPAcceleration())
        wait_for_settling = message.get("wait_for_settling", True)
        return_timing = message.get("return_timing", False)
        if return_timing:
            bp_stage.logging_start()
        start_time = time.time()
        if mode == "absolute":
            bp_stage.threadedBPMove(
                log,
                distance,
                speed=speed,
                acceleration=acceleration,
                wait_for_settling=wait_for_settling,
                relative=False,
            )
        elif mode == "relative":
            bp_stage.threadedBPMove(
                log,
                distance,
                speed=speed,
                acceleration=acceleration,
                wait_for_settling=wait_for_settling,
                relative=True,
            )
        stop_time = time.time()
        if return_timing:
            bp_stage.logging_stop()
        socketio.emit(
            "bp_done",
            bp_get_position(return_timing=return_timing, notify=False),
            namespace="/manual",
        )
    except Exception as ex:
        log.warn("BP stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "bp", namespace="/manual")


@socketio.on("bp_start_jog", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def bp_start_jog(message):
    """Start jogging the main Z stage."""
    try:
        global start_time
        speed = float(message["speed"])
        start_time = time.time()
        bp_stage.startBPJog(speed=speed, acceleration=bp_stage.getDefaultBPAcceleration())
    except Exception as ex:
        log.warn("BP stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "bp", namespace="/manual")


@socketio.on("bp_stop_jog", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def bp_stop_jog():
    """Stop jogging the main Z stage"""
    try:
        global stop_time
        bp_stage.stopBPJog()
        stop_time = time.time()
        socketio.emit("bp_done", bp_get_position(notify=False), namespace="/manual")
    except Exception as ex:
        log.warn("BP stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "bp", namespace="/manual")


@socketio.on("bp_get_position", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def bp_get_position(return_timing=False, notify=True):
    """Get the position the main Z stage in um"""
    try:
        position = bp_stage.getBPPosition()
        limits = bp_stage.getBPLimits()
        ret_dict = {
            "position": f"{position*1000:.1f}",
            "limits": f"{limits[0]*1000:.1f}, {limits[1]*1000:.1f}",
        }
        if return_timing:
            times, positions = bp_stage.get_logging_results()
            ret_dict["start_time"] = start_time
            ret_dict["stop_time"] = stop_time
            ret_dict["times"] = times
            ret_dict["positions"] = positions
        if notify:
            socketio.emit("bp_return_position", ret_dict, namespace="/manual")
        return ret_dict
    except Exception as ex:
        log.warn("BP stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "bp", namespace="/manual")
        return {}
