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

# Generate HTML snippit list
manual_controls_data = {}
manual_controls_data["html_paths"] = {}

for key in config_dict.keys():
    if key == "light_engines":
        manual_controls_data[key] = {}
        key = "light_engine"
        manual_controls_data["html_paths"][key] = f"generic_drivers/{key}/{key}_snip.html"
    elif key == "stages":
        for key in config_dict["stages"].keys():
            manual_controls_data[key] = {}
            manual_controls_data["html_paths"][key] = f"generic_drivers/{key}/{key}_snip.html"
    else:
        manual_controls_data[key] = {}
        path = f"{key}/{key}_snip.html"
        if exists(f"{Config.PRINT_SERVER_FOLDER}/drivers/{path}"):
            manual_controls_data["html_paths"][key] = path

# Dynamically import python snippits
if "coord_systems" in config_dict.keys():
    import printer_server.drivers.coord_systems.coord_systems_snip
if "external_control" in config_dict.keys():
    import printer_server.drivers.external_control.external_control_snip
if "gpio" in config_dict.keys():
    import printer_server.drivers.gpio.gpio_snip
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
    
if "light_engines" in config_dict.keys():
    import printer_server.drivers.generic_drivers.light_engine.light_engine_snip
if "bp_stage" in config_dict["stages"].keys():
    import printer_server.drivers.generic_drivers.bp_stage.bp_stage_snip
if "focus_stage" in config_dict["stages"].keys():
    import printer_server.drivers.generic_drivers.focus_stage.focus_stage_snip
if "ttr_stage" in config_dict["stages"].keys():
    import printer_server.drivers.generic_drivers.ttr_stage.ttr_stage_snip
if "xy_stage" in config_dict["stages"].keys():
    import printer_server.drivers.generic_drivers.xy_stage.xy_stage_snip

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
        manual_controls_data["external_control"]["enabled"] = enabled

    if initialized:
        if "coord_systems" in config_dict:
            # set active coord system
            coord_system_name, _ = printer_server.drivers.coord_systems.coord_systems_snip.get_coodinate_system()
            manual_controls_data["coord_systems"]["active"] = coord_system_name
            # set coord system list
            manual_controls_data["coord_systems"]["coord_systems"] = {}
            for key in config_dict["coord_systems"].keys():
                manual_controls_data["coord_systems"]["coord_systems"][key] = config_dict["coord_systems"][key]

        if "gpio" in config_dict.keys():
            if "film_pin" in config_dict["gpio"].keys():
                manual_controls_data["gpio"][
                    "film_state"
                ] = printer_server.drivers.gpio.gpio_snip.getFilmRelayState()

        if "keyence" in config_dict.keys():
            sensors = list(config_dict["keyence"]["sensors"].keys())
            manual_controls_data["keyence"]["sensors"] = sensors
            manual_controls_data["keyence"]["readings"] = {}
            manual_controls_data["keyence"]["focus"] = {}
            for sensor in sensors:
                sensor_reading = printer_server.drivers.keyence.keyence_snip.read_sensor(
                    config_dict["keyence"]["sensors"][sensor]["measurement_index"]
                )
                manual_controls_data["keyence"]["readings"][sensor] = sensor_reading

        if "loadcell" in config_dict.keys():
            manual_controls_data["loadcell"][
                "autoscale"
            ] = printer_server.drivers.loadcell.loadcell_snip.get_graph_autoscale()
            manual_controls_data["loadcell"][
                "in_newtons"
            ] = printer_server.drivers.loadcell.loadcell_snip.get_graph_mode()

        if "mks" in config_dict.keys():
            relay_setting = printer_server.drivers.mks.mks_snip.get_relay_status(emit=False)
            manual_controls_data["mks"]["relay_setting"] = relay_setting
            manual_controls_data["mks"]["gauge"] = printer_server.drivers.mks.mks_snip.get_gauges(emit=False)
            manual_controls_data["mks"]["target"] =config_dict["mks"]["target"]
            manual_controls_data["mks"]["atm"] = config_dict["mks"]["atm pressure"]-50
            manual_controls_data["mks"]["crane_pos"] = printer_server.drivers.mks.mks_snip.cranePosition(emit=False)

        if "photodiode" in config_dict.keys():
            default_wavelength = config_dict["photodiode"]["default_wavelength"]
            manual_controls_data["photodiode"]["power"] = printer_server.drivers.photodiode.photodiode_snip.get_photodiode_power({"wavelength": default_wavelength}, emit=False)
            manual_controls_data["photodiode"]["wavelength"] = default_wavelength 

        if "spectrometer" in config_dict.keys():
            manual_controls_data["spectrometer"]["default_integrations"] = config_dict["spectrometer"]["default_integration_time"]
            manual_controls_data["spectrometer"]["default_averages"] = config_dict["spectrometer"]["default_number_of_averages"]

        # screen and light engines
        if "light_engines" in config_dict.keys() or "screen" in config_dict.keys():
            for light_engine in config_dict["light_engines"]:
                manual_controls_data["light_engines"][light_engine] = {}
                if light_engine in config_dict.keys():
                    manual_controls_data["light_engines"][light_engine][
                        "status"
                    ] = printer_server.drivers.generic_drivers.light_engine.light_engine_snip.getLedStatus(light_engine)
                    manual_controls_data["light_engines"][light_engine]["dual_led"] = config_dict[light_engine]["dual_led"]
                    manual_controls_data["light_engines"][light_engine]["leds_nm"] = config_dict[light_engine]["leds_nm"]

        if "bp_stage" in config_dict["stages"].keys():
            manual_controls_data["bp_stage"] = printer_server.drivers.generic_drivers.bp_stage.bp_stage_snip.bp_get_position(notify=False)

        if "focus_stage" in config_dict["stages"].keys():
            manual_controls_data["focus_stage"] = printer_server.drivers.generic_drivers.focus_stage.focus_stage_snip.focus_get_position(notify=False)

        if "ttr_stage" in config_dict["stages"].keys():
            manual_controls_data["ttr_stage"] = printer_server.drivers.generic_drivers.ttr_stage.ttr_stage_snip.ttr_get_position(notify=False)

        if "xy_stage" in config_dict["stages"].keys():
            manual_controls_data["xy_stage"] = printer_server.drivers.generic_drivers.xy_stage.xy_stage_snip.xy_get_position(notify=False)
            
    return render_template(
        "manual_controls.html",
        initialized=initialized,
        hostname=Config.HOSTNAME,
        manual_controls_data=manual_controls_data,
    )


@blueprint.route("screen_image_upload", methods=["POST"])
def upload():
    return printer_server.drivers.screen.screen_snip.handleUpload(request)


def update_le_led_state(le, state):
    socketio.emit(f"light_engine_update_led_state", {"light_engine": le, "state":state}, namespace="/manual")
