from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict
import printer_server.views.manual_controls

xy_stage = driver_handles.xy_stage
if "coord_systems" in config_dict:
    from printer_server.drivers.coord_systems.coord_systems_snip import coord_systems_control
else:
    coord_systems_control = None
    
@socketio.on("xy_set_coodinate_system", namespace="/manual")
def xy_set_coodinate_system(message):
    "Set coordinate system offsets"
    global coord_system
    coord_system = config_dict["coord_systems"][message]
    socketio.emit(
        "xy_done", xy_get_position(notify=False), namespace="/manual"
    )

@socketio.on("xy_home", namespace="/manual")
def xy_home():
    """Home xy stage."""
    xy_stage.home()
    socketio.emit(
        "xy_done", xy_get_position(notify=False), namespace="/manual"
    )

@socketio.on("xy_move", namespace="/manual")
def xy_move(message):
    """Move the xy stage in um"""
    mode = message["mode"]
    distance = float(message["distance"]) / 1000
    axis = message.get("axis",None)
    speed = message.get("speed", xy_stage.getDefaultXYSpeed(axis))
    acceleration = message.get("acceleration", xy_stage.getDefaultXYAcceleration(axis))
    wait_for_settling=message.get("wait_for_settling", True)
    if mode == "absolute":
        if coord_systems_control is not None:
            coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
            calibration_positions = printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
            if "wintech" in coord_system_name:
                distance += coord_system[axis]
                if axis == "X":
                    y_distance = xy_stage.getXYPosition(axis="Y") - coord_system["Y"]
                    distance += calibration_positions.get("x_drift",0)/1000 + calibration_positions.get("x_shift",0)*y_distance/1000
                if axis == "Y":
                    x_distance = xy_stage.getXYPosition(axis="X") - coord_system["X"]
                    distance += calibration_positions.get("y_drift",0)/1000 + calibration_positions.get("y_shift",0)*x_distance/1000
            else:
                distance += coord_system[axis]
            
        xy_stage.absMoveXY(mm=distance, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)
    elif mode == "relative":
        xy_stage.relMoveXY(mm=distance, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling, axis=axis)
    socketio.emit(
        "xy_done", xy_get_position(notify=False), namespace="/manual"
    )

@socketio.on("xy_get_position", namespace="/manual")
def xy_get_position(notify=True):
    """Get the position the xy stage in um."""
    positions = {}
    for axis in ["X", "Y"]:
        position = xy_stage.getXYPosition(axis=axis)
        if coord_systems_control is not None:
            coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
            calibration_positions = printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
            if "wintech" in coord_system_name:
                position -= coord_system[axis]
                position *= 1000
                if axis == "X":
                    y_position = xy_stage.getXYPosition(axis="Y") - coord_system["Y"]
                    position -= calibration_positions.get("x_drift",0.0) + calibration_positions.get("x_shift",0.0)*y_position
                if axis == "Y":
                    x_position = xy_stage.getXYPosition(axis="X") - coord_system["X"]
                    position -= calibration_positions.get("y_drift",0.0) + calibration_positions.get("y_shift",0.0)*x_position
            else:
                position -= coord_system[axis]
                position *= 1000
        positions[axis] = {
            "position": f"{position:.1f}"
        }
    if notify:
        socketio.emit("xy_return_position", positions, namespace="/manual")
    return positions