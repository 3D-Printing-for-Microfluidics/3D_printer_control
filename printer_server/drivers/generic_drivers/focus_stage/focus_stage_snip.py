from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict
import printer_server.views.manual_controls

import time

focus_stage = driver_handles.focus_stage
if "coord_systems" in config_dict:
    from printer_server.drivers.coord_systems.coord_systems_snip import coord_systems_control
else:
    coord_systems_control = None

@socketio.on("focus_set_coodinate_system", namespace="/manual")
def focus_set_coodinate_system(message):
    "Set coordinate system offsets"
    global coord_system
    coord_system = config_dict["coord_systems"][message]
    socketio.emit(
        "focus_done", focus_get_position(notify=False), namespace="/manual"
    )

@socketio.on("focus_home", namespace="/manual")
def focus_home():
    """Home focus stage."""
    focus_stage.home()
    socketio.emit(
        "focus_done", focus_get_position(notify=False), namespace="/manual"
    )

@socketio.on("focus_move", namespace="/manual")
def focus_move(message):
    """Move the focus stage in um."""
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

@socketio.on("focus_get_position", namespace="/manual")
def focus_get_position(notify=True):
    """Get the position the focus stage in um"""
    position = focus_stage.getFocusPosition()
    if coord_systems_control is not None:
        coord_system_name, coord_system = coord_systems_control.get_coodinate_system()
        position -= coord_system["Focus"]
        position *= 1000
    positions = {
        "position": f"{position:.1f}"
    }
    if notify:
        socketio.emit("focus_return_position", positions, namespace="/manual")

    return positions







# import threading

# from printer_server.hardware_configuration.hardware_configuration import driver_handles
# from printer_server.extensions import socketio
# from printer_server.threading_wrapper import Thread
# import printer_server.views.manual_controls

# kdc = driver_handles.kdc101

# # log = logging.getLogger(__name__)
# # log.setLevel(logging.INFO)

# @socketio.on("get_kdc_positions", namespace="/manual")
# def get_kdc_positions(log=False, emit=True):
#     last_positions = (
#         printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
#     )
#     last_positions["distance"] = kdc.getCurrentPos()

#     if log:
#         printer_server.views.manual_controls.write_to_position_log(last_positions)
#     if emit:
#         socketio.emit(
#             "kdc_done",
#             last_positions,
#             namespace="/manual"
#         )

#     return last_positions

# @socketio.on("kdc_motor_move", namespace="/manual")
# def moveKDCMotor(message):
#     distance_um = float(message["microns"])
#     mode = message["mode"]
#     mode = (
#         mode != "absolute"
#     )  # convert mode to True/False, absolute is true, all else is false
#     kdc.move(distance_um, relative=mode)
#     get_kdc_positions(log=message["log"])

# @socketio.on("kdc_motor_home", namespace="/manual")
# def homeKDCMotor(message):
#     axis = message["axis"]

#     def func(axis):
#         kdc.home()
#         get_kdc_positions(log=True)

#     t = Thread(name="kdc101_snip_home_thread", target=func, args=[axis])
#     t.start()
