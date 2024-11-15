"""Control view."""
import json
from pathlib import Path
from datetime import datetime
from os.path import exists
from flask import request, Blueprint, render_template
import logging

from printer_server.extensions import socketio
from printer_server.settings import Config
from printer_server.threading_wrapper import Thread
import printer_server.views.home
from printer_server.hardware_configuration.hardware_configuration import config_dict

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

conversion_dict = {
    "Focus": "focus",
    "Visitech Focus": "keyence_visitech",
    "Wintech Focus": "keyence_wintech",
    "Tip": "tip",
    "Tilt": "tilt",
    "Rotate": "rotate",
    "Pivot X": "pivot_x",
    "Pivot Y": "pivot_y",
    "Pivot Z": "pivot_z",
    "Wintech X drift": "x_drift",
    "Wintech Y drift": "y_drift",
    "Wintech X Shift per mm Y": "xy_shift",
    "Wintech Y Shift per mm X": "yx_shift",
    "Wintech X Shift per mm X": "xx_shift",
    "Wintech Y Shift per mm Y": "yy_shift",
}

position_log_file = str(Path.cwd() / "logs" / "calibration_position_log.txt")

def write_to_position_log(message):
    with open(position_log_file, "a") as f:
        f.write(
            "{} {}\n".format(
                datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), json.dumps(message)
            )
        )


def get_last_calibration_positions_from_logs():
    """Return the last focused position from the position log file.
    """
    log_file = Path(Config.PROJECT_ROOT) / "logs" / "calibration_position_log.txt"
    last_line = None
    try:
        with open(log_file) as f:
            for line in f:
                last_line = line.rstrip()

        last_line = last_line[20:]
        last_line = last_line.replace("'", '"')
        temp = json.loads(last_line)
        return temp
    except FileNotFoundError:
        return {}
    
def human_to_machine(human_string):
    # Normalize the input by replacing underscores with spaces
    normalized = human_string.replace('-', ' ')
    # Convert to machine-readable string
    return conversion_dict.get(normalized)

def machine_to_human(machine_string):
    # Reverse lookup in the dictionary
    for human, machine in conversion_dict.items():
        if machine == machine_string:
            return human
    return None

# Create bluprint
blueprint = Blueprint(
    "calibration",
    __name__,
    url_prefix="/",
    template_folder="../drivers",
    static_folder="../drivers",
)

def create_calibration_data():
    calibration_data = {}

    def add_to_dict(l):
        for setting in l:
            calibration_data[machine_to_human(setting)] = last_positions.get(setting, 0.0)

    last_positions = get_last_calibration_positions_from_logs()
    # Use dynamic focus if available
    if "keyence" in config_dict.keys():
        keyence_sensors = []
        for sensor in config_dict["keyence"]["sensors"].keys():
            setting = f"keyence_{sensor}"
            if setting not in conversion_dict.values():
                conversion_dict[f"{sensor.capitalize()} Focus"] = setting
            keyence_sensors.append(setting)
        add_to_dict(keyence_sensors)
    else:
        add_to_dict(["focus"])

    # Add TTR axis (if hexapod also add pivot)
    if "hexapod" in config_dict.keys():
        add_to_dict(["tip", "tilt", "rotate", "pivot_x", "pivot_y", "pivot_z"])
    else:
        add_to_dict(["tip", "tilt"])
    
    # Add wintech correction
    if "wintech" in config_dict.keys():
        add_to_dict(["x_drift", "y_drift", "xy_shift", "yx_shift", "xx_shift", "yy_shift"])

    return calibration_data


# Decorator to handle navigation to calibration page
@blueprint.route("/calibration")
def index():
    initialized = printer_server.views.home.print_control.state != "uninitialized"

    return render_template(
        "calibration.html",
        initialized=initialized,
        hostname=Config.HOSTNAME,
        calibration_data=create_calibration_data(),
    )

@socketio.on("set", namespace="/calibration")
def set(message):
    mode = message["mode"]
    distance = float(message["distance"])
    parameter = message.get("parameter",None)
    last_positions = get_last_calibration_positions_from_logs()
    if mode == "absolute":
        last_positions[human_to_machine(parameter)] = round(distance,1)
    elif mode == "relative":
        last_positions[human_to_machine(parameter)] = round(distance + last_positions.get(human_to_machine(parameter),0.0),1)
    write_to_position_log(last_positions)
    socketio.emit(
        "set_done", create_calibration_data(), namespace="/calibration"
    )

@socketio.on("goto", namespace="/calibration")
def goto():
    from printer_server.hardware_configuration.hardware_configuration import driver_handles
    calibration_positions = get_last_calibration_positions_from_logs()

    focus = calibration_positions.get("focus",0)
    tip = calibration_positions.get("tip",0)
    tilt = calibration_positions.get("tilt",0)
    rotate = calibration_positions.get("rotate",0)
    pivot_x = calibration_positions.get("pivot_x",0)
    pivot_y = calibration_positions.get("pivot_y",0)
    pivot_z = calibration_positions.get("pivot_z",0)

    focus /= 1000
    tip /= 1000
    tilt /= 1000
    rotate /= 1000

    
    # move tt to 0
    driver_handles.ttr_stage.threadedTTRMove(log, 0, 0, 0)

    # set hexapod pivot
    x = pivot_x/1000
    y = pivot_y/1000
    z = pivot_z/1000
    driver_handles.hexapod.set_pivot_point(x,y,z)

    # move ttr
    ttr_threads = driver_handles.ttr_stage.threadedTTRMove(log, tip, tilt, rotate, join=False)

    # move focus (if not dynamic)
    focus_thread = driver_handles.focus_stage.threadedFocusMove(log, focus, join=False)

    for thread in ttr_threads:
        thread.join()
        if thread.exception is not None:
            raise thread.exception
    focus_thread.join()
    if focus_thread.exception is not None:
        raise focus_thread.exception

    socketio.emit(
        "goto_done", create_calibration_data(), namespace="/calibration"
    )
