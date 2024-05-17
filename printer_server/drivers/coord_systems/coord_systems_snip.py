from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles
import printer_server.views.manual_controls

coord_systems_control = driver_handles.coord_systems_control


@socketio.on("set_coodinate_system", namespace="/manual")
def set_coodinate_system(message):
    """set_coodinate_system -- Sets the variable determining which coordinate system to use"""
    coord_systems_control.set_coodinate_system(message),


def get_coodinate_system(emit=True):
    """Return the current coordinate system."""
    coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
    return coord_system_name, coord_system

@socketio.on("set_wintech_adjustments", namespace="/manual")
def set_wintech_adjustments(message):

    last_positions = (
        printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
    )

    for k,v in message.items():
        if type(v) is int or type(v) is float:
            last_positions[k] = v

    printer_server.views.manual_controls.write_to_position_log(last_positions)

    socketio.emit(
        "wintech_adj_update",
        last_positions,
        namespace="/manual",
        broadcast=True,
    )