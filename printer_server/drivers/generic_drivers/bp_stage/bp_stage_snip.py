from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict
import printer_server.views.manual_controls

import time

bp_stage = driver_handles.bp_stage
if "coord_systems" in config_dict:
    from printer_server.drivers.coord_systems.coord_systems_snip import coord_systems_control
else:
    coord_systems_control = None

start_time = 0
stop_time = 0
@socketio.on("bp_set_coodinate_system", namespace="/manual")
def bp_set_coodinate_system(message):
    "Set coordinate system offsets"
    global coord_system
    coord_system = config_dict["coord_systems"][message]
    socketio.emit(
        "bp_done", bp_get_position(notify=False), namespace="/manual"
    )

@socketio.on("bp_go_to_top", namespace="/manual")
def bp_go_to_top():
    """Move main Z stage to max position (up)."""
    global start_time, stop_time
    start_time = time.time()
    bp_stage.goToBPtop()
    stop_time = time.time()
    socketio.emit(
        "bp_done", bp_get_position(notify=False), namespace="/manual"
    )

@socketio.on("bp_home", namespace="/manual")
def bp_home():
    """Home main z stage."""
    global start_time, stop_time
    start_time = time.time()
    bp_stage.home()
    stop_time = time.time()
    socketio.emit(
        "bp_done", bp_get_position(notify=False), namespace="/manual"
    )

@socketio.on("bp_move", namespace="/manual")
def bp_move(message):
    """Move the main Z stage in um."""
    global start_time, stop_time
    mode = message["mode"]
    distance = float(message["distance"]) / 1000
    speed = message.get("speed", bp_stage.getDefaultBPSpeed())
    acceleration = message.get("acceleration", bp_stage.getDefaultBPAcceleration())
    wait_for_settling=message.get("wait_for_settling", True)
    return_timing=message.get("return_timing",False)
    if return_timing:
        bp_stage.logging_start()
    start_time = time.time()
    if mode == "absolute":
        if coord_systems_control is not None:
            coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
            distance += coord_system["Build Platform"]
            
        bp_stage.absMoveBP(mm=distance, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling)
    elif mode == "relative":
        bp_stage.relMoveBP(mm=distance, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling)
    stop_time = time.time()
    if return_timing:
        bp_stage.logging_stop()
    socketio.emit(
        "bp_done", bp_get_position(return_timing=return_timing, notify=False), namespace="/manual"
    )


@socketio.on("bp_start_jog", namespace="/manual")
def bp_start_jog(message):
    """Start jogging the main Z stage."""
    global start_time
    speed = float(message["speed"])
    start_time = time.time()
    bp_stage.startBPJog(speed=speed, acceleration=bp_stage.getDefaultBPAcceleration())


@socketio.on("bp_stop_jog", namespace="/manual")
def bp_stop_jog():
    """Stop jogging the main Z stage"""
    global stop_time
    bp_stage.stopBPJog()
    stop_time = time.time()
    socketio.emit(
        "bp_done", bp_get_position(notify=False), namespace="/manual"
    )


@socketio.on("bp_get_position", namespace="/manual")
def bp_get_position(return_timing=False, notify=True):
    """Get the position the main Z stage in um"""
    position = bp_stage.getBPPosition()
    if coord_systems_control is not None:
        coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
        position -= coord_system["Build Platform"]
        position *= 1000
    ret_dict = {
        "position":f"{position:.1f}"
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