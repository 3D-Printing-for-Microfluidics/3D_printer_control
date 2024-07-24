from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles, config_dict
import printer_server.views.manual_controls

import time

galil = driver_handles.galil
try:
    coord_systems_control = driver_handles.coord_systems_control
except:
    coord_systems_control = None
start_time = 0
stop_time = 0
@socketio.on("galil_set_coodinate_system", namespace="/manual")
def galil_set_coodinate_system(message):
    "Set coordinate system offsets"
    global coord_system
    coord_system = config_dict["coord_systems"][message]
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual"
    )

@socketio.on("galil_go_to_calibration", namespace="/manual")
def galil_go_to_calibration():
    """Move main Z stage to default position with calibration system."""
    global start_time, stop_time
    start_time = time.time()
    galil.goToBPcalibration()
    stop_time = time.time()
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual"
    )


@socketio.on("galil_go_to_top", namespace="/manual")
def galil_go_to_top():
    """Move main Z stage to max position (up)."""
    global start_time, stop_time
    start_time = time.time()
    galil.goToBPmax()
    stop_time = time.time()
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual"
    )


@socketio.on("galil_go_to_bottom", namespace="/manual")
def galil_go_to_bottom():
    """Move main z stage to min position (down)."""
    global start_time, stop_time
    start_time = time.time()
    galil.goToBPmin()
    stop_time = time.time()
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual"
    )


@socketio.on("galil_home", namespace="/manual")
def home():
    """Home main z stage."""
    global start_time, stop_time
    start_time = time.time()
    galil.home()
    stop_time = time.time()
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual"
    )


@socketio.on("galil_move", namespace="/manual")
def galil_move(message):
    """Move the main Z stage. All units in mm."""
    global start_time, stop_time
    mode = message["mode"]
    distance = float(message["distance"]) / 1000
    axis = message["axis"]
    speed = message.get("speed", galil.getDefaultSpeed(axis))
    acceleration = message.get("acceleration", galil.getDefaultAcceleration(axis))
    wait_for_settling=message.get("wait_for_settling", True)
    return_timing=message.get("return_timing",False)
    if return_timing:
        galil.logging_start()
    start_time = time.time()
    if mode == "absolute":
        if coord_systems_control is not None:
            coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
            calibration_positions = printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
            if "wintech" in coord_system_name:
                distance += coord_system[galil.getCommonName(axis)]
                #position *= 1000
                if galil.getCommonName(axis) == "X":
                    y_distance = galil.getPosition(in_mm=True, axis="Y") - coord_system["Y"]
                    distance += calibration_positions.get("x_drift",0)/1000 + calibration_positions.get("x_shift",0)*y_distance/1000
                if galil.getCommonName(axis) == "Y":
                    x_distance = galil.getPosition(in_mm=True, axis="X") - coord_system["X"]
                    distance += calibration_positions.get("y_drift",0)/1000 + calibration_positions.get("y_shift",0)*x_distance/1000
            else:
                distance += coord_system[galil.getCommonName(axis)]
            
        galil.absMove(mm=distance, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)
    elif mode == "relative":
        galil.relMove(mm=distance, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)
    stop_time = time.time()
    if return_timing:
        galil.logging_stop()
    socketio.emit(
        "galil_done", galil_get_positions(return_timing), namespace="/manual"
    )


@socketio.on("galil_start_jog", namespace="/manual")
def galil_startJog(message):
    """Start jogging the main Z stage."""
    global start_time
    speed = float(message["speed"])
    start_time = time.time()
    galil.startJog(speed=speed, acceleration=galil.getDefaultAcceleration())


@socketio.on("galil_stop_jog", namespace="/manual")
def galil_stopJog():
    """Stop jogging the main Z stage"""
    global stop_time
    galil.stopJog()
    stop_time = time.time()
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual"
    )


def galil_get_positions(return_timing=False):
    """Get the position the main Z stage."""
    positions = {}
    for axis in galil.axes:
        position = galil.getPosition(in_mm=True, axis=axis)
        if coord_systems_control is not None:
            coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
            calibration_positions = printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
            if "wintech" in coord_system_name:
                position -= coord_system[galil.getCommonName(axis)]
                position *= 1000
                if galil.getCommonName(axis) == "X":
                    y_position = galil.getPosition(in_mm=True, axis="Y") - coord_system["Y"]
                    position -= calibration_positions.get("x_drift",0.0) + calibration_positions.get("x_shift",0.0)*y_position
                if galil.getCommonName(axis) == "Y":
                    x_position = galil.getPosition(in_mm=True, axis="X") - coord_system["X"]
                    position -= calibration_positions.get("y_drift",0.0) + calibration_positions.get("y_shift",0.0)*x_position
            else:
                position -= coord_system[galil.getCommonName(axis)]
                position *= 1000
        positions[axis] = f"{position:.1f}"
    if return_timing:
        positions["start_time"] = start_time
        positions["stop_time"] = stop_time
        positions["times"] = galil.movement_log_times
        positions["positions"] = galil.movement_log_array
    return positions


@socketio.on("galil_get_position", namespace="/manual")
def galil_get_position(axis, notify=True):
    """Get the position the main Z stage."""
    a = galil.convertAxis(axis)
    if notify:
        message = {"position": galil.getPosition(in_mm=True)}
        socketio.emit("galil_return_position", message, namespace="/manual")
    return galil.getPosition(in_mm=True, axis=a)
