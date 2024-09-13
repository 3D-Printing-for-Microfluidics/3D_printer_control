from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict
import printer_server.views.manual_controls

ttr_stage = driver_handles.ttr_stage

@socketio.on("ttr_home", namespace="/manual")
def ttr_home():
    """Home ttr stage."""
    ttr_stage.home()
    socketio.emit(
        "ttr_done", ttr_get_position(notify=False), namespace="/manual"
    )

@socketio.on("ttr_move", namespace="/manual")
def ttr_move(message):
    """Move the ttr stage in rad."""
    mode = message["mode"]
    distance = float(message["distance"])/1000
    axis = message.get("axis",None)
    if mode == "absolute":      
        ttr_stage.absMoveTTR(rad=distance, axis=axis)
    elif mode == "relative":
        ttr_stage.relMoveTTR(rad=distance, axis=axis)  
    socketio.emit(
        "ttr_done", ttr_get_position(notify=False), namespace="/manual"
    )

@socketio.on("ttr_get_position", namespace="/manual")
def ttr_get_position(notify=True):
    """Get the position the ttr stage in rad."""
    positions = {}
    for axis in ttr_stage.axes_common_names:
        if axis in ["Tip", "Tilt", "Rotate"]:
            position = ttr_stage.getTTRPosition(axis=axis)
            positions[axis] = {
                "position": f"{position*1000:.1f}"
            }
    if notify:
        socketio.emit("xy_return_position", positions, namespace="/manual")
    return positions