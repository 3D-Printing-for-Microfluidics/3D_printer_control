import printer_server.views.manual_controls
from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles

keyence = driver_handles.keyence


@socketio.on("keyence_setpoint_update", namespace="/manual")
def updateSetpoint(message):
    sensor = message["sensor"]
    distance_um = float(message["microns"])
    mode = message["mode"]
    mode = mode != "absolute"

    last_positions = (
        printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
    )

    if mode:
        last_positions[f"keyence_{sensor}"] = (
            float(last_positions.get(f"keyence_{sensor}",0)) + distance_um
        )
    else:
        last_positions[f"keyence_{sensor}"] = distance_um

    printer_server.views.manual_controls.write_to_position_log(last_positions)

    socketio.emit(
        "keyence_setpoint_updated",
        last_positions,
        namespace="/manual"
    )


def read_sensor(index):
    """Returns the readout of the given sensor in um"""
    return keyence.read_sensor(index)
