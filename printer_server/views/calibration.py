"""Control view."""
import json
from pathlib import Path
from datetime import datetime
from os.path import exists
from flask import request, Blueprint, render_template

from printer_server.extensions import socketio
from printer_server.settings import Config
import printer_server.views.home
from printer_server.hardware_configuration.hardware_configuration import config_dict

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
    "Wintech X Shift per mm Y": "x_shift",
    "Wintech Y Shift per mm X": "y_shift",
}

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

    if "hexapod" in config_dict.keys():
        add_to_dict(["tip", "tilt", "rotate", "pivot_x", "pivot_y", "pivot_z"])
    else:
        add_to_dict(["tip", "tilt"])
    
    if "wintech" in config_dict.keys():
        add_to_dict(["x_drift", "y_drift", "x_shift", "y_shift"])

    return calibration_data


# Decorator to handle navigation to calibration page
@blueprint.route("/calibration")
def index():
    return render_template(
        "calibration.html",
        hostname=Config.HOSTNAME,
        calibration_data=create_calibration_data(),
    )

@socketio.on("set", namespace="/calibration")
def set(message):
    """Move the xy stage in um"""
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
    











#     @socketio.on("coodinate_system_set_wintech_adjustments", namespace="/manual")
# def set_wintech_adjustments(message):

#     last_positions = (
#         printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
#     )

#     for k,v in message.items():
#         if type(v) is int or type(v) is float:
#             last_positions[k] = v

#     printer_server.views.manual_controls.write_to_position_log(last_positions)

#     socketio.emit(
#         "coodinate_system_done",
#         last_positions,
#         namespace="/manual"
#     )
    

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
    

#     @socketio.on("keyence_set_setpoint", namespace="/manual")
# def updateSetpoint(message):
#     sensor = message["sensor"]
#     distance_um = float(message["microns"])
#     mode = message["mode"]
#     mode = mode != "absolute"

#     last_positions = (
#         printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
#     )

#     if mode:
#         last_positions[f"keyence_{sensor}"] = (
#             float(last_positions.get(f"keyence_{sensor}",0)) + distance_um
#         )
#     else:
#         last_positions[f"keyence_{sensor}"] = distance_um

#     printer_server.views.manual_controls.write_to_position_log(last_positions)

#     socketio.emit(
#         "keyence_done",
#         last_positions,
#         namespace="/manual"
#     )
