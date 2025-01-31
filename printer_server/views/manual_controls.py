"""Control view."""
import json
import time
import logging
from threading import Event
from pathlib import Path
from datetime import datetime
from os.path import exists
from flask import request, Blueprint, render_template

from printer_server.extensions import socketio
from printer_server.settings import Config
import printer_server.views.home
from printer_server.threading_wrapper import Thread
from printer_server.hardware_configuration.hardware_configuration import config_dict

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

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

connected_clients = 0
on_load_f_no_init = []
on_load_f_init = []
on_load_f_looping = []
loop_thread = None
loop_stop_event = Event()

# env, acc

# Dynamically import python snippits
if "coord_systems" in config_dict.keys():
    import printer_server.drivers.coord_systems.coord_systems_snip
    on_load_f_init.append(
        printer_server.drivers.coord_systems.coord_systems_snip.get_coodinate_system
    )

if "bp_stage" in config_dict["stages"].keys():
    import printer_server.drivers.generic_drivers.bp_stage.bp_stage_snip
    on_load_f_init.append(
        printer_server.drivers.generic_drivers.bp_stage.bp_stage_snip.bp_get_position
    )

if "focus_stage" in config_dict["stages"].keys():
    import printer_server.drivers.generic_drivers.focus_stage.focus_stage_snip
    on_load_f_init.append(
        printer_server.drivers.generic_drivers.focus_stage.focus_stage_snip.focus_get_position
    )

if "ttr_stage" in config_dict["stages"].keys():
    import printer_server.drivers.generic_drivers.ttr_stage.ttr_stage_snip
    on_load_f_init.append(
        printer_server.drivers.generic_drivers.ttr_stage.ttr_stage_snip.ttr_get_position
    )

if "xy_stage" in config_dict["stages"].keys():
    import printer_server.drivers.generic_drivers.xy_stage.xy_stage_snip
    on_load_f_init.append(
        printer_server.drivers.generic_drivers.xy_stage.xy_stage_snip.xy_get_position
    )

if "external_control" in config_dict.keys():
    import printer_server.drivers.external_control.external_control_snip
    on_load_f_init.append(
        printer_server.drivers.external_control.external_control_snip.get_external_control_enable
    )
    on_load_f_no_init.append(
        printer_server.drivers.external_control.external_control_snip.get_external_control_enable
    )

if "gpio" in config_dict.keys():
    import printer_server.drivers.gpio.gpio_snip
    if "film_pin" in config_dict["gpio"].keys():
        on_load_f_init.append(
            printer_server.drivers.gpio.gpio_snip.getFilmRelayState
        )

if "keyence" in config_dict.keys():
    import printer_server.drivers.keyence.keyence_snip
    on_load_f_init.append(
        printer_server.drivers.keyence.keyence_snip.read_sensors
    )
    on_load_f_looping.append(
        printer_server.drivers.keyence.keyence_snip.read_sensors
    )

if "loadcell" in config_dict.keys():
    import printer_server.drivers.loadcell.loadcell_snip
    on_load_f_init.append(
        printer_server.drivers.loadcell.loadcell_snip.get_graph_mode
    )

if "mks" in config_dict.keys() and "mks_teensy" in config_dict.keys():
    import printer_server.drivers.mks.mks_snip  
    on_load_f_init.extend([
        printer_server.drivers.mks.mks_snip.load_mks,
        printer_server.drivers.mks.mks_snip.get_relay_status,
        printer_server.drivers.mks.mks_snip.get_gauges,
        printer_server.drivers.mks.mks_snip.cranePosition
    ])
    on_load_f_looping.extend([
        printer_server.drivers.mks.mks_snip.get_relay_status,
        printer_server.drivers.mks.mks_snip.get_gauges,
        printer_server.drivers.mks.mks_snip.cranePosition
    ])

if "photodiode" in config_dict.keys():
    import printer_server.drivers.photodiode.photodiode_snip
    on_load_f_init.append(
        printer_server.drivers.photodiode.photodiode_snip.get_photodiode_power
    )
    on_load_f_looping.append(
        printer_server.drivers.photodiode.photodiode_snip.get_photodiode_power
    )

if "screen" in config_dict.keys():
    import printer_server.drivers.screen.screen_snip
    on_load_f_init.append(
        printer_server.drivers.screen.screen_snip.screenLoad
    )
    on_load_f_init.append(
        printer_server.drivers.screen.screen_snip.screenFetchPreviews
    )

if "spectrometer" in config_dict.keys():
    import printer_server.drivers.spectrometer.spectrometer_snip
    on_load_f_init.append(
        printer_server.drivers.spectrometer.spectrometer_snip.spectrometer_load
    )

if "light_engines" in config_dict.keys():
    import printer_server.drivers.generic_drivers.light_engine.light_engine_snip
    on_load_f_init.append(
        printer_server.drivers.generic_drivers.light_engine.light_engine_snip.getLedStatus
    )


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

    # Create list/dicts for Jinja2 loading
    if "coord_systems" in config_dict:
        manual_controls_data["coord_systems"] = list(config_dict["coord_systems"].keys())

    if "gpio" in config_dict.keys():
        manual_controls_data["gpio"] = list(config_dict["gpio"].keys())

    if "keyence" in config_dict.keys():
        manual_controls_data["keyence"] = list(config_dict["keyence"]["sensors"].keys())

    if "light_engines" in config_dict.keys() or "screen" in config_dict.keys():
        for light_engine in config_dict["light_engines"]:
            manual_controls_data["light_engines"][light_engine] = {}
            if light_engine in config_dict.keys():
                manual_controls_data["light_engines"][light_engine]["dual_led"] = config_dict[light_engine]["dual_led"]
                manual_controls_data["light_engines"][light_engine]["leds_nm"] = config_dict[light_engine]["leds_nm"]
                
    if "xy_stage" in config_dict["stages"].keys():
        manual_controls_data["xy_stage"] = printer_server.drivers.generic_drivers.xy_stage.xy_stage_snip.xy_get_stage_list()

    if "ttr_stage" in config_dict["stages"].keys():
        manual_controls_data["ttr_stage"] = printer_server.drivers.generic_drivers.ttr_stage.ttr_stage_snip.ttr_get_stage_list()
            
    return render_template(
        "manual_controls.html",
        initialized=initialized,
        hostname=Config.HOSTNAME,
        manual_controls_data=manual_controls_data,
    ) 

@socketio.on("connect", namespace="/manual")
def connect():
    log.debug("MC Socket connected %s", request.sid)
    global loop_thread, connected_clients

    if loop_thread is None:
        connected_clients = 1
    else:
        connected_clients += 1

    if printer_server.views.home.print_control.state != "uninitialized":
        for f in on_load_f_init:
            f()
        if loop_thread is None:
            start_loop()
    else:
        for f in on_load_f_no_init:
            f()

@socketio.on("disconnect", namespace="/manual")
def disconnect():
    log.debug("MC Socket disconnected %s", request.sid)
    global connected_clients
    if connected_clients > 0:
        connected_clients -= 1
    stop_loop()

def start_loop():
    global loop_thread, loop_stop_event
    loop_stop_event.clear()
    loop_thread = Thread(log, name="manual_control_loop_thread", target=loop)
    loop_thread.start()

def loop():
    global loop_thread, connected_clients, loop_stop_event
    _on_load_f_looping = on_load_f_looping.copy()
    while connected_clients > 0 and not loop_stop_event.is_set():
        if not _on_load_f_looping:
            return
        for f in _on_load_f_looping[:]:
            try:
                ret_val = f()
                if ret_val is None:
                    _on_load_f_looping.remove(f)
            except RuntimeError as ex:
                log.warning("Manual Control loop failed (%s)", ex, exc_info=True)
                loop_thread = None
                return
            except Exception as ex:
                pass
        time.sleep(0.5)

def stop_loop(force=False):
    global loop_thread, connected_clients, loop_stop_event
    if connected_clients <= 0 or force:
        if loop_thread is not None:
            loop_stop_event.set()
            loop_thread.join()
            loop_thread = None


@blueprint.route("screen_image_upload", methods=["POST"])
def upload():
    return printer_server.drivers.screen.screen_snip.handleUpload(request)


def update_le_led_state(le, state):
    socketio.emit(f"light_engine_update_led_state", {"light_engine": le, "state":state}, namespace="/manual")

def update_screen_preview(light_engine, preview):
    previews = {light_engine: preview}
    socketio.emit(
        "screen_previews", previews, namespace="/manual"
    )