"""Control view."""
import json
from pathlib import Path
from datetime import datetime
from os.path import exists
from flask import request, Blueprint, render_template
from printer_server.drivers.galil.galil_snip import (
    galil_get_positions,
)

from printer_server.extensions import socketio
from printer_server.settings import Config
import printer_server.views.home


# Dynamically get hardware components
configuration_path = Path(Config.PRINT_SERVER_FOLDER).rglob("hardware_configuration.json")
with open(next(configuration_path), "r") as file_handle:
    config_dict = json.load(file_handle)
config_dict = config_dict[Config.HOSTNAME]

light_engines = []
# Dynamically import python snippits
if "external_control" in config_dict.keys():
    import printer_server.drivers.external_control.external_control_snip
if "galil" in config_dict.keys():
    import printer_server.drivers.galil.galil_snip
if "kdc101" in config_dict.keys():
    import printer_server.drivers.kdc101.kdc101_snip
if "loadcell" in config_dict.keys():
    import printer_server.drivers.loadcell.loadcell_snip
if "screen" in config_dict.keys():
    import printer_server.drivers.screen.screen_snip
if "tiptilt" in config_dict.keys():
    import printer_server.drivers.tiptilt.tiptilt_snip
if "visitech" in config_dict.keys():
    import printer_server.drivers.visitech.visitech_snip
# if "wintech" in config_dict.keys():
#     import printer_server.drivers.wintech.wintech_snip


# Generate HTML snippit list
hardware_partials = {}
for key in config_dict.keys():
    path = f"{key}/{key}_snip.html"
    if exists(f"{Config.PRINT_SERVER_FOLDER}/drivers/{path}"):
        hardware_partials[key] = f"{path}"


# Create bluprint
blueprint = Blueprint(
    "manual_controls",
    __name__,
    url_prefix="/",
    template_folder="../drivers",
    static_folder="../drivers",
)

# Decorator to handle navigation to calibration page
@blueprint.route("/manual")
def index():
    initialized = printer_server.views.home.print_control.state != "uninitialized"
    calibration_positions = get_last_calibration_positions()
    galil_stages = {}
    if initialized:
        galil_positions = galil_get_positions()
        for i in range(len(config_dict["galil"]["axes"])):
            axis = config_dict["galil"]["axes"][i]
            galil_stages[axis] = {
                "common": config_dict["galil"]["axes_common_names"][i],
                "position": galil_positions[axis],
            }

    return render_template(
        "manual_controls.html",
        initalized=initialized,
        hostname=Config.HOSTNAME,
        hardware=hardware_partials,
        light_engines=config_dict["screen"]["light_engines"],
        galil_stages=galil_stages,
        calibration_positions=calibration_positions,
    )


@blueprint.route("handle-calibration-upload", methods=["POST"])
def upload():
    return printer_server.drivers.screen.screen_snip.handleUpload(request)


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
    return {
        "tip": float(last_line.split(" ")[-5]),
        "tilt": float(last_line.split(" ")[-3]),
        "distance": float(last_line.split(" ")[-1]),
    }
