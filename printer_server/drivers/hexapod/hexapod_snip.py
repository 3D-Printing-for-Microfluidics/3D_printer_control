import logging
import os
from datetime import datetime
from flask import Flask, render_template
from flask_socketio import SocketIO
from hexapod import Hexapod

def create_driver_logs_folder():
    # ============ Create folder for the logs of the current system run ============
    # Parent Directory path
    parent_folder = os.getcwd()

    log_folder_name = "logs"
    logs_path_folder = os.path.join(parent_folder, log_folder_name)

    now = datetime.now()
    log_run_folder = now.strftime("%m-%d-%Y__%H-%M-%S")

    
    # Path to new folder
    path_including_new_folder = os.path.join(logs_path_folder, log_run_folder)
    
    # # Create the directory
    os.makedirs(path_including_new_folder)
    # print(f"Log folder for system run created: {path_including_new_folder}")

    # Create local directory to be used for file creation
    local_log_run_directory = os.path.join(logs_path_folder, log_run_folder)

    return local_log_run_directory

PIVOT_SET_COMMAND = "pivot"
TRANSLATION_COMMAND = "translation"
ROTATION_COMMAND = "rotation"

app = Flask(__name__)

# This section gets rid of console messages from the server (that way we don't loose error messages from the system in development after a long run time)
app.logger.disabled = True
log = logging.getLogger('werkzeug')
log.disabled = True
logging.getLogger("socketio").setLevel(logging.ERROR)
logging.getLogger("engineio").setLevel(logging.ERROR)

log_directory = create_driver_logs_folder() # Create folder for log files

socketio = SocketIO()
socketio.init_app(app)

hexapod = Hexapod(log_directory)


@app.route("/")
@app.route("/manual_control")
def manual_control():
    return render_template("manual_control.html")

@socketio.on("initialize_hexapod")
def initialize_hexapod():
    print(f"Init command received")

    hexapod.connect()
    init_flag = hexapod.check_initialization()
    if (init_flag):
        error_codes = hexapod.get_status()
        pivot_update = hexapod.get_pivot_point()
        pose_update = hexapod.get_pose()
        
    else:
        error_codes = None
        pivot_update = None
        pose_update = None

    socketio.emit("init_msg", [init_flag, error_codes, pivot_update, pose_update])

@socketio.on("check_init")
def check_init():
    print(f"check_init received")

    init_flag = hexapod.check_initialization()
    if (init_flag):
        error_codes = hexapod.get_status()
        pivot_update = hexapod.get_pivot_point()
        pose_update = hexapod.get_pose()
        
    else:
        error_codes = None
        pivot_update = None
        pose_update = None

    socketio.emit("init_msg", [init_flag, error_codes, pivot_update, pose_update])

@socketio.on("stop_motion")
def stop_motion():
    print(f"Stop command received")

    hexapod.hard_stop()
    pose_update = hexapod.get_pose()

    socketio.emit("pose_update", pose_update)

@socketio.on("axis_step")
def axis_step(step_information):
    print(f"step_information: {step_information}")

    command_type = step_information[0]
    axis = step_information[1]
    value = step_information[2]

    # Perform hexapod command
    if (command_type == PIVOT_SET_COMMAND):
        hexapod.step_pivot_point(axis, value)
        pivot_update = hexapod.get_pivot_point()
        socketio.emit("pivot_update", pivot_update)

    elif (command_type == TRANSLATION_COMMAND) or (command_type == ROTATION_COMMAND):
        hexapod.step_axis(axis, value)
        pose_update = hexapod.get_pose()
        socketio.emit("pose_update", pose_update)        

@socketio.on("pivot_command")
def pivot_command(pivot_information):
    print(f"pivot_information: {pivot_information}")

    x_pivot_pos = pivot_information[0]
    y_pivot_pos = pivot_information[1]
    z_pivot_pos = pivot_information[2]

    hexapod.set_pivot_point(x_pivot_pos, y_pivot_pos, z_pivot_pos)
    pivot_update = hexapod.get_pivot_point()

    socketio.emit("pivot_update", pivot_update)

@socketio.on("pose_command")
def pose_command(pose_information):
    print(f"pose_information: {pose_information}")

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

    socketio.emit("pose_update", pose_update)

@socketio.on("request_dynamic_ranges")
def request_dynamic_ranges():
    print(f"SERVER: request_dynamic_ranges()")

    # hexapod.interesting_functions()
    hexapod.get_simple_dynamic_range('X')
    hexapod.get_simple_dynamic_range('Y')
    hexapod.get_simple_dynamic_range('Z')
    hexapod.get_simple_dynamic_range('U')
    hexapod.get_simple_dynamic_range('V')
    hexapod.get_simple_dynamic_range('W')