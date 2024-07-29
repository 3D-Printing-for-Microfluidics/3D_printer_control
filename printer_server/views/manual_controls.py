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
configuration_path = Path(Config.PRINT_SERVER_FOLDER).joinpath('hardware_configuration').rglob(f"{Config.HOSTNAME}.json")
with open(next(configuration_path), "r") as file_handle:
    config_dict = json.load(file_handle)

# Generate HTML snippit list
hardware = {}
for key in config_dict.keys():
    path = f"{key}/{key}_snip.html"
    if exists(f"{Config.PRINT_SERVER_FOLDER}/drivers/{path}"):
        temp_dict = {"path": f"{path}"}
        hardware[key] = temp_dict

# Dynamically import python snippits
if "acs" in config_dict.keys():
    import printer_server.drivers.acs.acs_snip
if "coord_systems" in config_dict.keys():
    import printer_server.drivers.coord_systems.coord_systems_snip
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
if "mks" in config_dict.keys():
    import printer_server.drivers.mks.mks_snip
if "photodiode" in config_dict.keys():
    import printer_server.drivers.photodiode.photodiode_snip
if "screen" in config_dict.keys():
    import printer_server.drivers.screen.screen_snip
if "spectrometer" in config_dict.keys():
    import printer_server.drivers.spectrometer.spectrometer_snip
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
        calibration_positions = get_last_calibration_positions_from_logs()
        if "coord_systems" in config_dict:
            # set active coord system
            coord_system_name, _ = printer_server.drivers.coord_systems.coord_systems_snip.get_coodinate_system()
            hardware["coord_systems"]["active"] = coord_system_name
            # set coord system list
            hardware["coord_systems"]["coord_systems"] = {}
            for key in config_dict["coord_systems"].keys():
                hardware["coord_systems"]["coord_systems"][key] = config_dict["coord_systems"][key]
            # set coord adjustments
            if "wintech" in config_dict.keys():
                hardware["coord_systems"]["coord_adjustments"] = {
                    "x_drift": {"name": "X Drift", "value":calibration_positions.get("x_drift",0.0)},
                    "y_drift": {"name": "Y Drift", "value":calibration_positions.get("y_drift",0.0)},
                    "x_shift": {"name": "X Shift per mm Y", "value":calibration_positions.get("x_shift",0.0)},
                    "y_shift": {"name": "Y Shift per mm X", "value":calibration_positions.get("y_shift",0.0)}
                }

        if "acs" in config_dict.keys():
            acs_positions = (
                printer_server.drivers.acs.acs_snip.acs_get_positions()
            )
            hardware["acs"]["stages"] = {}
            for i in range(len(config_dict["acs"]["axes"])):
                axis = config_dict["acs"]["axes"][i]
                hardware["acs"]["stages"][axis] = {
                    "common": config_dict["acs"]["axes_common_names"][i],
                    "position": acs_positions[axis],
                }

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

        if "gpio" in config_dict.keys():
            if "film_pin" in config_dict["gpio"].keys():
                hardware["gpio"][
                    "film_state"
                ] = printer_server.drivers.gpio.gpio_snip.getFilmRelayState()

        if "kdc101" in config_dict.keys():
            hardware["kdc101"]["distance"] = calibration_positions.get("distance",0)

        if "keyence" in config_dict.keys():
            sensors = list(config_dict["keyence"]["sensors"].keys())
            hardware["keyence"]["sensors"] = sensors
            hardware["keyence"]["readings"] = {}
            hardware["keyence"]["focus"] = {}
            for sensor in sensors:
                sensor_reading = printer_server.drivers.keyence.keyence_snip.read_sensor(
                    config_dict["keyence"]["sensors"][sensor]["measurement_index"]
                )
                hardware["keyence"]["focus"][sensor] = calibration_positions.get(
                    f"keyence_{sensor}", 0
                )
                hardware["keyence"]["readings"][sensor] = sensor_reading

        if "loadcell" in config_dict.keys():
            hardware["loadcell"][
                "autoscale"
            ] = printer_server.drivers.loadcell.loadcell_snip.get_graph_autoscale()
            hardware["loadcell"][
                "in_newtons"
            ] = printer_server.drivers.loadcell.loadcell_snip.get_graph_mode()

        if "mks" in config_dict.keys():
            relay_setting, relay_status = printer_server.drivers.mks.mks_snip.get_relay_status()
            hardware["mks"]["relay_setting"] = relay_setting
            hardware["mks"]["relay_status"] = relay_status
            hardware["mks"]["gauge"] = printer_server.drivers.mks.mks_snip.get_gauges()
            hardware["mks"]["target"] =config_dict["mks"]["target"]
            hardware["mks"]["atm"] = config_dict["mks"]["atm pressure"]-50
            hardware["mks"]["crane_pos"] = printer_server.drivers.mks.mks_snip.cranePosition(emit=False)

        if "photodiode" in config_dict.keys():
            default_wavelength = config_dict["photodiode"]["default_wavelength"]
            hardware["photodiode"]["power"] = printer_server.drivers.photodiode.photodiode_snip.get_photodiode_power({"wavelength": default_wavelength}, emit=False)
            hardware["photodiode"]["wavelength"] = default_wavelength 

        if "screen" in config_dict.keys():
            hardware["light_engines"] = config_dict["light_engines"]

        if "spectrometer" in config_dict.keys():
            hardware["spectrometer"]["default_integrations"] = config_dict["spectrometer"]["default_integration_time"]
            hardware["spectrometer"]["default_averages"] = config_dict["spectrometer"]["default_number_of_averages"]

        if "tiptilt" in config_dict.keys():
            hardware["tiptilt"]["tip"] = calibration_positions.get("tip",0)
            hardware["tiptilt"]["tilt"] = calibration_positions.get("tilt",0)

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
        initialized=initialized,
        hostname=Config.HOSTNAME,
        hardware=hardware,
    )


@blueprint.route("screen_image_upload", methods=["POST"])
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


def get_last_calibration_positions_from_logs():
    """Return the last focused position for the distance axis from the
    position log file.
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


def update_le_led_state(le, state):
    socketio.emit(f"{le}_update_led_state", state, namespace="/manual")
