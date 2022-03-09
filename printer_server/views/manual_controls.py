# -*- coding: utf-8 -*-
"""Control view."""
import json
from pathlib import Path
from datetime import datetime
from os.path import exists
from flask import request, Blueprint, render_template

from printer_server.extensions import socketio
from printer_server.settings import Config


class External_Control:
    def __init__(self):
        self.enable_flag = False

    def set_enable(self, status):
        self.enable_flag = status

    def get_enable(self):
        return self.enable_flag


external_control_enable = External_Control()

# Dynamically get hardware components
configuration_path = Path(Config.PRINT_SERVER_FOLDER).rglob("hardware_configuration.json")
with open(next(configuration_path), "r") as file_handle:
    config_dict = json.load(file_handle)
config_dict = config_dict[Config.HOSTNAME]

# Dynamically import python snippits
if "galil" in config_dict.keys():
    import printer_server.drivers.galil.galil_snip
if "kdc101" in config_dict.keys():
    import printer_server.drivers.kdc101.kdc101_snip
# if "loadcell" in config_dict.keys():
#     import printer_server.drivers.loadcell.loadcell_snip
if "screen" in config_dict.keys():
    import printer_server.drivers.screen.screen_snip
if "tiptilt" in config_dict.keys():
    import printer_server.drivers.tiptilt.tiptilt_snip
if "visitech" in config_dict.keys():
    import printer_server.drivers.visitech.visitech_snip
# if "wintech" in config_dict.keys():
#     import printer_server.drivers.wintech.wintech_snip


# Generate HTML snippit list
hardware_partials = []
for key in config_dict.keys():
    path = f"{key}/{key}_snip.html"
    if exists(f"{Config.PRINT_SERVER_FOLDER}/drivers/{path}"):
        hardware_partials.append(f"../{path}")


# Create bluprint
blueprint = Blueprint(
    "manual_controls",
    __name__,
    url_prefix="/",
    template_folder="../drivers",
    static_folder="../static",
)

# Decorator to handle navigation to calibration page
@blueprint.route("/manual")
def index():
    positions = get_last_calibration_positions()
    return render_template(
        "manual_controls.html",
        tip_position=positions[0],
        tilt_position=positions[1],
        dist_position=positions[2],
        hostname=Config.HOSTNAME,
        hardware=hardware_partials,
    )


@blueprint.route("handle-calibration-upload", methods=["POST"])
def upload():
    printer_server.drivers.screen.screen_snip.handleUpload(request)


@socketio.on("set_external_control_enable", namespace="/manual")
def set_external_control_enable(message):
    """set_external_control -- Sets the variable determining if printer can be auto-calibrated"""
    external_control_enable.set_enable(message == "Enabled")


@socketio.on("get_external_control_enable", namespace="/manual")
def get_external_control_enable():
    """Return the external control enable flag."""
    socketio.emit(
        "external_control_enable",
        external_control_enable.get_enable(),
        namespace="/manual",
        broadcast=True,
    )


position_log_file = str(Path.cwd() / "logs" / "calibration_position_log.txt")


def write_to_position_log(message):
    with open(position_log_file, "a") as f:
        f.write("{} {}\n".format(datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), message))


def get_last_calibration_positions():
    """Return the last focused position for the distance axis from the
    position log file.
    """
    log_file = Path(Config.PROJECT_ROOT) / "logs" / "calibration_position_log.txt"
    last_line = None
    with open(log_file) as f:
        for line in f:
            last_line = line.rstrip()
    for char in ["{", "}", ":", "'", ","]:
        last_line = last_line.replace(char, "")
    return [
        float(last_line.split(" ")[-5]),
        float(last_line.split(" ")[-3]),
        float(last_line.split(" ")[-1]),
    ]
