import printer_server.views.manual_controls
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles

hexapod = driver_handles.hexapod

PIVOT_SET_COMMAND = "pivot"
TRANSLATION_COMMAND = "translation"
ROTATION_COMMAND = "rotation"

@socketio.on("hexapod_get_positions", namespace="/manual")
def get_hexapod_positions(emit=True, log=False):
    last_positions = (
        printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
    )

    new_tip = hexapod.get_pose("Tip")*1000
    new_tilt = hexapod.get_pose("Tilt")*1000
    new_rotate = hexapod.get_pose("Rotate")*1000

    if new_tip is not None:
        last_positions["tip"] = new_tip
        last_positions["tilt"] = new_tilt
        last_positions["rotate"] = new_rotate

    if log:
        printer_server.views.manual_controls.write_to_position_log(last_positions)

    if emit:
        socketio.emit(
            "hexapod_done",
            last_positions,
            namespace="/manual"
        )

    return last_positions

@socketio.on("initialize_hexapod", namespace="/manual")
def initialize_hexapod():
    init_flag = hexapod.initialized
    if (init_flag):
        error_codes = hexapod.get_status()
        pivot_update = hexapod.get_pivot_point()
        pose_update = hexapod.get_pose()
        
    else:
        error_codes = None
        pivot_update = None
        pose_update = None

    socketio.emit("init_msg", [init_flag, error_codes, pivot_update, pose_update], namespace="/manual")

@socketio.on("check_init", namespace="/manual")
def check_init():
    init_flag = hexapod.initialized
    if (init_flag):
        error_codes = hexapod.get_status()
        pivot_update = hexapod.get_pivot_point()
        pose_update = hexapod.get_pose()
        
    else:
        error_codes = None
        pivot_update = None
        pose_update = None

    socketio.emit("init_msg", [init_flag, error_codes, pivot_update, pose_update], namespace="/manual")

@socketio.on("stop_motion", namespace="/manual")
def stop_motion():
    hexapod.hard_stop()
    pose_update = hexapod.get_pose()

    socketio.emit("pose_update", pose_update, namespace="/manual")

@socketio.on("axis_step", namespace="/manual")
def axis_step(step_information):
    command_type = step_information[0]
    axis = step_information[1]
    value = step_information[2]

    # Perform hexapod command
    if (command_type == PIVOT_SET_COMMAND):
        hexapod.step_pivot_point(axis, value)
        pivot_update = hexapod.get_pivot_point()
        socketio.emit("pivot_update", pivot_update, namespace="/manual")

    elif (command_type == TRANSLATION_COMMAND) or (command_type == ROTATION_COMMAND):
        hexapod.step_axis(axis, value)
        pose_update = hexapod.get_pose()
        socketio.emit("pose_update", pose_update, namespace="/manual")    
        get_hexapod_positions(log=True)

@socketio.on("pivot_command", namespace="/manual")
def pivot_command(pivot_information):
    x_pivot_pos = pivot_information[0]
    y_pivot_pos = pivot_information[1]
    z_pivot_pos = pivot_information[2]

    hexapod.set_pivot_point(x_pivot_pos, y_pivot_pos, z_pivot_pos)
    pivot_update = hexapod.get_pivot_point()

    socketio.emit("pivot_update", pivot_update, namespace="/manual")

@socketio.on("pose_command", namespace="/manual")
def pose_command(pose_information):
    x = pose_information[0]
    y = pose_information[1]
    z = pose_information[2]
    u = pose_information[3]
    v = pose_information[4]
    w = pose_information[5]

    hexapod.move_to_position_compound(x, y, z)
    hexapod.move_to_angle_compound(u, v, w)
    # hexapod.set_pose(x, y, z, u, v, w)
    pose_update = hexapod.get_pose()

    socketio.emit("pose_update", pose_update, namespace="/manual")
    get_hexapod_positions(log=True)

@socketio.on("request_dynamic_ranges", namespace="/manual")
def request_dynamic_ranges():
    ranges = {
        "X": hexapod.get_simple_dynamic_range('X'),
        "Y": hexapod.get_simple_dynamic_range('Y'),
        "Z": hexapod.get_simple_dynamic_range('Z'),
        "U": hexapod.get_simple_dynamic_range('U'),
        "V": hexapod.get_simple_dynamic_range('V'),
        "W": hexapod.get_simple_dynamic_range('W')
    }
    socketio.emit("dynamic_ranges", ranges, namespace="/manual")