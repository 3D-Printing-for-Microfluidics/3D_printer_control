import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict
from printer_server.views.calibration import (
    get_last_calibration_positions_from_logs,
)

xy_stage = driver_handles.xy_stage
if "coord_systems" in config_dict:
    from printer_server.drivers.coord_systems.coord_systems_snip import coord_systems_control
else:
    coord_systems_control = None

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
    
@socketio.on("xy_set_coodinate_system", namespace="/manual")
def xy_set_coodinate_system(message):
    "Set coordinate system offsets"
    try:
        global coord_system
        coord_system = config_dict["coord_systems"][message]
        socketio.emit(
            "xy_done", xy_get_position(notify=False), namespace="/manual"
        )
    except Exception as ex:
        log.warn("XY stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "xy", namespace="/manual")

@socketio.on("xy_home", namespace="/manual")
def xy_home():
    """Home xy stage."""
    try:
        xy_stage.home()
        socketio.emit(
            "xy_done", xy_get_position(notify=False), namespace="/manual"
        )
    except Exception as ex:
        log.warn("XY stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "xy", namespace="/manual")

@socketio.on("xy_move", namespace="/manual")
def xy_move(message):
    """Move the xy stage in um"""
    try:
        mode = message["mode"]
        distance = float(message["distance"]) / 1000
        axis = message.get("axis",None)
        speed = message.get("speed", xy_stage.getDefaultXYSpeed(axis))
        acceleration = message.get("acceleration", xy_stage.getDefaultXYAcceleration(axis))
        wait_for_settling=message.get("wait_for_settling", True)
        if mode == "absolute":
            if coord_systems_control is not None:
                coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
                calibration_positions = get_last_calibration_positions_from_logs()
                if "wintech" in coord_system_name:
                    distance += coord_system[axis]

                    x_distance = xy_stage.getXYPosition(axis="X") - coord_system["X"]
                    y_distance = xy_stage.getXYPosition(axis="Y") - coord_system["Y"]
                    if axis == "X":
                        distance += calibration_positions.get("x_drift",0)/1000 + calibration_positions.get("xy_shift",0)*y_distance/1000 + calibration_positions.get("xx_shift",0)*x_distance/1000
                    if axis == "Y":
                        distance += calibration_positions.get("y_drift",0)/1000 + calibration_positions.get("yx_shift",0)*x_distance/1000 + calibration_positions.get("yy_shift",0)*y_distance/1000
                else:
                    distance += coord_system[axis]
                
            xy_stage.absMoveXY(mm=distance, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)
        elif mode == "relative":
            xy_stage.relMoveXY(mm=distance, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)
        socketio.emit(
            "xy_done", xy_get_position(notify=False), namespace="/manual"
        )
    except Exception as ex:
        log.warn("XY stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "xy", namespace="/manual")

def xy_get_stage_list():
    stages = []
    for axis in xy_stage.axes_common_names:
        if axis in ["X", "Y"]:
            stages.append(axis)
    return stages

@socketio.on("xy_get_position", namespace="/manual")
def xy_get_position(notify=True):
    """Get the position the xy stage in um."""
    try:
        positions = {}
        for axis in xy_stage.axes_common_names:
            if axis in ["X", "Y"]:
                position = xy_stage.getXYPosition(axis=axis)
                limits = xy_stage.getXYLimits(axis=axis)
                if coord_systems_control is not None:
                    coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
                    calibration_positions = get_last_calibration_positions_from_logs()
                    if "wintech" in coord_system_name:
                        position -= coord_system[axis]
                        position *= 1000

                        x_position = xy_stage.getXYPosition(axis="X") - coord_system["X"]
                        y_position = xy_stage.getXYPosition(axis="Y") - coord_system["Y"]
                        if axis == "X":
                            position -= calibration_positions.get("x_drift",0.0) + calibration_positions.get("xy_shift",0.0)*y_position + calibration_positions.get("xx_shift",0.0)*x_position
                        if axis == "Y":
                            position -= calibration_positions.get("y_drift",0.0) + calibration_positions.get("yx_shift",0.0)*x_position + calibration_positions.get("yy_shift",0.0)*y_position
                    else:
                        position -= coord_system[axis]
                        position *= 1000
                positions[axis] = {
                    "position": f"{position:.1f}",
                    "limits": f"{limits[0]*1000:.1f}, {limits[1]*1000:.1f}"
                }
        if notify:
            socketio.emit("xy_return_position", positions, namespace="/manual")
        return positions
    except Exception as ex:
        log.warn("XY stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "xy", namespace="/manual")
        return {}