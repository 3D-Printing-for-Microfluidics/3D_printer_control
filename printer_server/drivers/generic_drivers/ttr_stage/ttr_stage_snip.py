import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict
import printer_server.views.manual_controls
from printer_server.views.users import socket_require_permissions

ttr_stage = driver_handles.ttr_stage

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

@socketio.on("ttr_home", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def ttr_home():
    """Home ttr stage."""
    try:
        ttr_stage.home()
        socketio.emit(
            "ttr_done", ttr_get_position(notify=False), namespace="/manual"
        )
    except Exception as ex:
        log.warn("TTR stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "ttr", namespace="/manual")

@socketio.on("ttr_move", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def ttr_move(message):
    """Move the ttr stage in rad."""
    try:
        mode = message["mode"]
        distance = float(message["distance"])/1000
        axis = message.get("axis",None)
        if mode == "absolute":      
            ttr_stage.threadedTTRMove(
                log,
                distance if axis == "Tip" else None,
                distance if axis == "Tilt" else None,
                distance if axis == "Rotate" else None,
                relative=False,
            )
        elif mode == "relative":
            ttr_stage.threadedTTRMove(
                log,
                distance if axis == "Tip" else None,
                distance if axis == "Tilt" else None,
                distance if axis == "Rotate" else None,
                relative=True,
            )
        socketio.emit(
            "ttr_done", ttr_get_position(notify=False), namespace="/manual"
        )
    except Exception as ex:
        log.warn("TTR stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "ttr", namespace="/manual")

def ttr_get_stage_list():
    stages = []
    for axis in ttr_stage.axes_common_names:
        if axis in ["Tip", "Tilt", "Rotate"]:
            stages.append(axis)
    return stages

@socketio.on("ttr_get_position", namespace="/manual")
@socket_require_permissions(permission="advanced", require_session=False)
def ttr_get_position(notify=True):
    """Get the position the ttr stage in rad."""
    try:
        positions = {}
        for axis in ttr_stage.axes_common_names:
            if axis in ["Tip", "Tilt", "Rotate"]:
                position = ttr_stage.getTTRPosition(axis=axis)
                limits = ttr_stage.getTTRLimits(axis=axis)
                if position != "undef":
                    positions[axis] = {
                        "position": f"{position*1000:.1f}",
                        "limits": f"{limits[0]*1000:.1f}, {limits[1]*1000:.1f}"
                    }
                else:
                    positions[axis] = {
                        "position": "undef",
                        "limits": f"{limits[0]*1000:.1f}, {limits[1]*1000:.1f}"
                    }
        if notify:
            socketio.emit("ttr_return_position", positions, namespace="/manual")
        return positions
    except Exception as ex:
        log.warn("TTR stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "ttr", namespace="/manual")
        return {}