from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles


galil = driver_handles.galil


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
    distance = float(message["distance"])/1000
    acceleration = float(message["acceleration"])
    axis = message["axis"]
    if mode == "absolute":
        galil.absMove(mm=distance, speed=speed, acceleration=acceleration, axis=axis)
    elif mode == "relative":
        galil.relMove(mm=distance, speed=speed, acceleration=acceleration, axis=axis)
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
        positions[axis] = galil.cntsToMm(galil.getPosition(axis=axis), axis=axis) * 1000
    return positions


@socketio.on("galil_get_position", namespace="/manual")
def galil_get_position(axis, notify=True):
    """Get the position the main Z stage."""
    a = galil.convertAxis(axis)
    if notify:
        message = {"position": galil.cntsToMm(galil.getPosition())}
        socketio.emit("galil_position", message, namespace="/manual", broadcast=True)
    return galil.cntsToMm(galil.getPosition(axis=a), axis=a)
