import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict
import printer_server.views.manual_controls

import time

focus_stage = driver_handles.focus_stage
if "coord_systems" in config_dict:
    from printer_server.drivers.coord_systems.coord_systems_snip import coord_systems_control
else:
    coord_systems_control = None

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

@socketio.on("focus_set_coodinate_system", namespace="/manual")
def focus_set_coodinate_system(message):
    "Set coordinate system offsets"
    try:
        global coord_system
        coord_system = config_dict["coord_systems"][message]
        socketio.emit(
            "focus_done", focus_get_position(notify=False), namespace="/manual"
        )
    except Exception as ex:
        log.warn("Focus stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "focus", namespace="/manual")

@socketio.on("focus_home", namespace="/manual")
def focus_home():
    """Home focus stage."""
    try:
        focus_stage.home()
        socketio.emit(
            "focus_done", focus_get_position(notify=False), namespace="/manual"
        )
    except Exception as ex:
        log.warn("Focus stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "focus", namespace="/manual")

@socketio.on("focus_move", namespace="/manual")
def focus_move(message):
    """Move the focus stage in um."""
    try:
        mode = message["mode"]
        distance = float(message["distance"]) / 1000
        speed = message.get("speed", focus_stage.getDefaultFocusSpeed())
        acceleration = message.get("acceleration", focus_stage.getDefaultFocusAcceleration())
        wait_for_settling=message.get("wait_for_settling", True)
        if mode == "absolute":
            if coord_systems_control is not None:
                coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
                distance += coord_system["Focus"]
                
            focus_stage.absMoveFocus(mm=distance, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling)
        elif mode == "relative":
            focus_stage.relMoveFocus(mm=distance, speed=speed, acceleration=acceleration, wait_for_settling=wait_for_settling)
        socketio.emit(
            "focus_done", focus_get_position(notify=False), namespace="/manual"
        )
    except Exception as ex:
        log.warn("Focus stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "focus", namespace="/manual")

@socketio.on("focus_get_position", namespace="/manual")
def focus_get_position(notify=True):
    """Get the position the focus stage in um"""
    try:
        position = focus_stage.getFocusPosition()
        limits = focus_stage.getFocusLimits()
        if coord_systems_control is not None:
            coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
            position -= coord_system["Focus"]
        positions = {
            "position": f"{position*1000:.1f}",
            "limits": f"{limits[0]*1000:.1f}, {limits[1]*1000:.1f}"
        }
        if notify:
            socketio.emit("focus_return_position", positions, namespace="/manual")

        return positions
    except Exception as ex:
        log.warn("Focus stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "focus", namespace="/manual")
        return {}