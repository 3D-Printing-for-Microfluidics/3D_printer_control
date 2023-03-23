"""Control view."""
import json
from pathlib import Path
from datetime import datetime
from os.path import exists
from flask import request, Blueprint, render_template

from printer_server.extensions import socketio
from printer_server.settings import Config
import printer_server.views.home


# Dynamically get hardware components
configuration_path = Path(Config.PRINT_SERVER_FOLDER).rglob("hardware_configuration.json")
with open(next(configuration_path), "r") as file_handle:
    config_dict = json.load(file_handle)
config_dict = config_dict[Config.HOSTNAME]

# Generate HTML snippit list
hardware = {}
for key in config_dict.keys():
    path = f"{key}/{key}_snip.html"
    if exists(f"{Config.PRINT_SERVER_FOLDER}/drivers/{path}"):
        temp_dict = {"path": f"{path}"}
        hardware[key] = temp_dict

# Dynamically import python snippits
if "external_control" in config_dict.keys():
    import printer_server.drivers.external_control.external_control_snip
if "galil" in config_dict.keys():
    import printer_server.drivers.galil.galil_snip
if "gpio" in config_dict.keys():
    import printer_server.drivers.gpio.gpio_snip
if "kdc101" in config_dict.keys():
    import printer_server.drivers.kdc101.kdc101_snip
if "keyence" in config_dict.keys():
    import printer_server.drivers.keyence.keyence_snip
if "loadcell" in config_dict.keys():
    import printer_server.drivers.loadcell.loadcell_snip
if "screen" in config_dict.keys():
    import printer_server.drivers.screen.screen_snip
if "tiptilt" in config_dict.keys():
    import printer_server.drivers.tiptilt.tiptilt_snip
if "visitech" in config_dict.keys():
    import printer_server.drivers.visitech.visitech_snip
if "wintech" in config_dict.keys():
    import printer_server.drivers.wintech.wintech_snip


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

    # Get driver status
    if "external_control" in config_dict.keys():
        enabled = printer_server.drivers.external_control.external_control_snip.get_external_control_enable(
            emit=False
        )
        hardware["external_control"]["enabled"] = enabled

    if initialized:
        calibration_positions = get_last_calibration_positions()
        if "galil" in config_dict.keys():
            galil_positions = (
                printer_server.drivers.galil.galil_snip.galil_get_positions()
            )
            hardware["galil"]["stages"] = {}
            for i in range(len(config_dict["galil"]["axes"])):
                axis = config_dict["galil"]["axes"][i]
                hardware["galil"]["stages"][axis] = {
                    "common": config_dict["galil"]["axes_common_names"][i],
                    "position": galil_positions[axis],
                }
            if "coord_systems" in config_dict["galil"]:
                hardware["galil"]["coord_systems"] = config_dict["galil"]["coord_systems"]
        if "gpio" in config_dict.keys():
            if "fan_pin" in config_dict["gpio"].keys():
                hardware["gpio"][
                    "fan_state"
                ] = printer_server.drivers.gpio.gpio_snip.getFanRelayState()
            if "film_pin" in config_dict["gpio"].keys():
                hardware["gpio"][
                    "film_state"
                ] = printer_server.drivers.gpio.gpio_snip.getFilmRelayState()
        if "kdc101" in config_dict.keys():
            hardware["kdc101"]["distance"] = calibration_positions["distance"]
        if "keyence" in config_dict.keys():
            sensors = list(config_dict["keyence"]["sensors"].keys())
            hardware["keyence"]["sensors"] = sensors
            hardware["keyence"]["readings"] = {}
            hardware["keyence"]["focus"] = {}
            for sensor in sensors:
                sensor_reading = printer_server.drivers.keyence.keyence_snip.read_sensor(
                    config_dict["keyence"]["sensors"][sensor]["measurement_index"]
                )
                hardware["keyence"]["focus"][sensor] = calibration_positions[
                    f"keyence_{sensor}"
                ]
                hardware["keyence"]["readings"][sensor] = sensor_reading

        if "loadcell" in config_dict.keys():
            hardware["loadcell"][
                "autoscale"
            ] = printer_server.drivers.loadcell.loadcell_snip.get_graph_autoscale()
            hardware["loadcell"][
                "in_newtons"
            ] = printer_server.drivers.loadcell.loadcell_snip.get_graph_mode()
        if "screen" in config_dict.keys():
            hardware["screen"]["light_engines"] = config_dict["screen"]["light_engines"]
        if "tiptilt" in config_dict.keys():
            hardware["tiptilt"]["tip"] = calibration_positions["tip"]
            hardware["tiptilt"]["tilt"] = calibration_positions["tilt"]
        if "visitech" in config_dict.keys():
            hardware["visitech"][
                "status"
            ] = printer_server.drivers.visitech.visitech_snip.getLedStatus()
            hardware["visitech"]["dual_led"] = config_dict["visitech"]["dual_led"]
            hardware["visitech"]["leds"] = config_dict["visitech"]["leds"]
        if "wintech" in config_dict.keys():
            hardware["wintech"][
                "status"
            ] = printer_server.drivers.wintech.wintech_snip.getLedStatus()

    return render_template(
        "manual_controls.html",
        initalized=initialized,
        hostname=Config.HOSTNAME,
        hardware=hardware,
    )


@blueprint.route("handle-calibration-upload", methods=["POST"])
def upload():
    return printer_server.drivers.screen.screen_snip.handleUpload(request)


position_log_file = str(Path.cwd() / "logs" / "calibration_position_log.txt")


def write_to_position_log(message):
    with open(position_log_file, "a") as f:
        f.write(
            "{} {}\n".format(
                datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), json.dumps(message)
            )
        )


def get_last_calibration_positions():
    """Return the last focused position for the distance axis from the
    position log file.
    """
    log_file = Path(Config.PROJECT_ROOT) / "logs" / "calibration_position_log.txt"
    last_line = None
    with open(log_file) as f:
        for line in f:
            last_line = line.rstrip()

    last_line = last_line[20:]
    last_line = last_line.replace("'", '"')
    temp = json.loads(last_line)
    return temp


def update_le_led_status(le, state):
    socketio.emit(f"update_{le}_led_status", state, namespace="/manual")
