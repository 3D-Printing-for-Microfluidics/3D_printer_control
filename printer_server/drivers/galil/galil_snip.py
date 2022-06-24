from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles
import printer_server.views.manual_controls

galil = driver_handles.galil
coord_system = None


@socketio.on("galil_set_coodinate_system", namespace="/manual")
def galil_set_coodinate_system(message):
    "Set coordinate system offsets"
    global coord_system
    coord_system = galil.config_dict["coord_systems"][message]
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual", broadcast=True
    )


@socketio.on("galil_go_to_calibration", namespace="/manual")
def galil_go_to_calibration():
    """Move main Z stage to default position with calibration system."""
    galil.goToZcalibration()
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual", broadcast=True
    )


@socketio.on("galil_go_to_top", namespace="/manual")
def galil_go_to_top():
    """Move main Z stage to max position (up)."""
    galil.goToZmax()
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual", broadcast=True
    )


@socketio.on("galil_go_to_bottom", namespace="/manual")
def galil_go_to_bottom():
    """Move main z stage to min position (down)."""
    galil.goToZmin()
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual", broadcast=True
    )


@socketio.on("galil_home", namespace="/manual")
def home():
    """Home main z stage."""
    galil.home()
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual", broadcast=True
    )


@socketio.on("galil_move", namespace="/manual")
def galil_move(message):
    """Move the main Z stage. All units in mm."""
    mode = message["mode"]
    speed = float(message["speed"])
    distance = float(message["distance"]) / 1000
    acceleration = float(message["acceleration"])
    axis = message["axis"]
    if mode == "absolute":
        global coord_system
        if coord_system is not None:
            distance += coord_system[galil.getCommonName(axis)]
        galil.absMove(mm=distance, speed=speed, acceleration=acceleration, axis=axis)
    elif mode == "relative":
        galil.relMove(mm=distance, speed=speed, acceleration=acceleration, axis=axis)
    if galil.getCommonName(axis) == "Focus":
        if message["log"] == True:
            printer_server.views.manual_controls.write_to_position_log(
                get_galil_focus_positions()
            )
        socketio.emit(
            "calibration_positions",
            get_galil_focus_positions(),
            namespace="/manual",
            broadcast=True,
        )
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual", broadcast=True
    )


@socketio.on("galil_start_jog", namespace="/manual")
def galil_startJog(message):
    """Start jogging the main Z stage."""
    speed = float(message["speed"])
    galil.startJog(speed=speed, acceleration=50)


@socketio.on("galil_stop_jog", namespace="/manual")
def galil_stopJog():
    """Stop jogging the main Z stage"""
    galil.stopJog()
    socketio.emit(
        "galil_done", galil_get_positions(), namespace="/manual", broadcast=True
    )


def galil_get_positions():
    """Get the position the main Z stage."""
    positions = {}
    for axis in galil.axes:
        position = galil.cntsToMm(galil.getPosition(axis=axis), axis=axis)
        global coord_system
        if coord_system is not None:
            position -= coord_system[galil.getCommonName(axis)]
        position *= 1000
        positions[axis] = f"{position:.1f}"
    return positions


def get_galil_focus_positions():
    last_positions = printer_server.views.manual_controls.get_last_calibration_positions()
    last_positions["distance"] = (
        galil.cntsToMm(galil.getPosition(axis="Focus"), axis="Focus") * 1000
    )
    return last_positions


@socketio.on("galil_get_position", namespace="/manual")
def galil_get_position(axis, notify=True):
    """Get the position the main Z stage."""
    a = galil.convertAxis(axis)
    if notify:
        message = {"position": galil.cntsToMm(galil.getPosition())}
        socketio.emit("galil_position", message, namespace="/manual", broadcast=True)
    return galil.cntsToMm(galil.getPosition(axis=a), axis=a)
