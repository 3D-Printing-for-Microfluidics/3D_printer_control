from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict
import printer_server.views.manual_controls

import time

acs = driver_handles.acs
if "coord_systems" in config_dict:
    from printer_server.drivers.coord_systems.coord_systems_snip import coord_systems_control
else:
    coord_systems_control = None

start_time = 0
stop_time = 0
@socketio.on("acs_set_coodinate_system", namespace="/manual")
def acs_set_coodinate_system(message):
    "Set coordinate system offsets"
    global coord_system
    coord_system = config_dict["coord_systems"][message]
    socketio.emit(
        "acs_done", acs_get_positions(), namespace="/manual"
    )

@socketio.on("acs_go_to_calibration", namespace="/manual")
def acs_go_to_calibration():
    """Move main Z stage to default position with calibration system."""
    global start_time, stop_time
    start_time = time.time()
    acs.goToBPcalibration()
    stop_time = time.time()
    socketio.emit(
        "acs_done", acs_get_positions(), namespace="/manual"
    )


@socketio.on("acs_go_to_top", namespace="/manual")
def acs_go_to_top():
    """Move main Z stage to max position (up)."""
    global start_time, stop_time
    start_time = time.time()
    acs.goToBPmax()
    stop_time = time.time()
    socketio.emit(
        "acs_done", acs_get_positions(), namespace="/manual"
    )


@socketio.on("acs_go_to_bottom", namespace="/manual")
def acs_go_to_bottom():
    """Move main z stage to min position (down)."""
    global start_time, stop_time
    start_time = time.time()
    acs.goToBPmin()
    stop_time = time.time()
    socketio.emit(
        "acs_done", acs_get_positions(), namespace="/manual"
    )


@socketio.on("acs_home", namespace="/manual")
def acs_home():
    """Home main z stage."""
    global start_time, stop_time
    start_time = time.time()
    acs.home()
    stop_time = time.time()
    socketio.emit(
        "acs_done", acs_get_positions(), namespace="/manual"
    )


@socketio.on("acs_move", namespace="/manual")
def acs_move(message):
    """Move the main Z stage. All units in mm."""
    global start_time, stop_time
    mode = message["mode"]
    distance = float(message["distance"]) / 1000
    axis = message.get("axis",None)
    speed = message.get("speed", acs.getDefaultSpeed(axis))
    acceleration = message.get("acceleration", acs.getDefaultAcceleration(axis))
    wait_for_settling=message.get("wait_for_settling", True)
    return_timing=message.get("return_timing",False)
    if return_timing:
        acs.logging_start()
    start_time = time.time()
    if mode == "absolute":
        if coord_systems_control is not None:
            coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
            calibration_positions = printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
            if "wintech" in coord_system_name:
                distance += coord_system[acs.getCommonName(axis)]
                #position *= 1000
                if acs.getCommonName(axis) == "X":
                    y_distance = acs.getPosition(axis="Y") - coord_system["Y"]
                    distance += calibration_positions.get("x_drift",0)/1000 + calibration_positions.get("x_shift",0)*y_distance/1000
                if acs.getCommonName(axis) == "Y":
                    x_distance = acs.getPosition(axis="X") - coord_system["X"]
                    distance += calibration_positions.get("y_drift",0)/1000 + calibration_positions.get("y_shift",0)*x_distance/1000
            else:
                distance += coord_system[acs.getCommonName(axis)]
            
        acs.absMove(mm=distance, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)
    elif mode == "relative":
        acs.relMove(mm=distance, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)
    stop_time = time.time()
    if return_timing:
        acs.logging_stop()
    socketio.emit(
        "acs_done", acs_get_positions(return_timing), namespace="/manual"
    )


@socketio.on("acs_start_jog", namespace="/manual")
def acs_start_jog(message):
    """Start jogging the main Z stage."""
    global start_time
    speed = float(message["speed"])
    start_time = time.time()
    acs.startJog(speed=speed, acceleration=acs.getDefaultAcceleration())


@socketio.on("acs_stop_jog", namespace="/manual")
def acs_stop_jog():
    """Stop jogging the main Z stage"""
    global stop_time
    acs.stopJog()
    stop_time = time.time()
    socketio.emit(
        "acs_done", acs_get_positions(), namespace="/manual"
    )


def acs_get_positions(return_timing=False):
    """Get the position the main Z stage."""
    positions = {}
    for axis in acs.axes:
        position = acs.getPosition(axis=axis)
        if coord_systems_control is not None:
            coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
            calibration_positions = printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
            if "wintech" in coord_system_name:
                position -= coord_system[acs.getCommonName(axis)]
                position *= 1000
                if acs.getCommonName(axis) == "X":
                    y_position = acs.getPosition(axis="Y") - coord_system["Y"]
                    position -= calibration_positions.get("x_drift",0.0) + calibration_positions.get("x_shift",0.0)*y_position
                if acs.getCommonName(axis) == "Y":
                    x_position = acs.getPosition(axis="X") - coord_system["X"]
                    position -= calibration_positions.get("y_drift",0.0) + calibration_positions.get("y_shift",0.0)*x_position
            else:
                position -= coord_system[acs.getCommonName(axis)]
                position *= 1000
        positions[axis] = f"{position:.1f}"
    if return_timing:
        positions["start_time"] = start_time
        positions["stop_time"] = stop_time
        positions["times"] = acs.movement_log_times
        positions["positions"] = acs.movement_log_array
    return positions


@socketio.on("acs_get_position", namespace="/manual")
def acs_get_position(axis, notify=True):
    """Get the position the main Z stage."""
    a = acs.convertAxis(axis)
    if notify:
        message = {"position": acs.getPosition()}
        socketio.emit("acs_return_position", message, namespace="/manual")
    return acs.getPosition(axis=a)
