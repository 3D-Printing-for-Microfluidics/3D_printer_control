import time
import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles, config_dict

mks = driver_handles.mks
mks_solenoids = driver_handles.mks_solenoids
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def get_gauges(emit=False):
    gauges = mks.read_all_pressures()
    if emit:
        socketio.emit(
            "pressure_readings_updated", {"gauge":gauges}, namespace="/manual"
        )
    return gauges

def get_relay_status(emit=False):
    relay_settings_list = mks.get_all_relay_status()
    solenoids_settings_list = mks_solenoids.get_all_relay_status()
    solenoids_status_list = mks_solenoids.get_all_switch_status()
    relay_settings_dict = {}
    relay_status_dict = {}
    for k, v in config_dict["mks"]["relays"].items():
        relay_settings_dict[k] = relay_settings_list[v["relay_num"]-1]

    for i, k in enumerate(config_dict["mks"]["solenoids"]):
        relay_settings_dict[k] = solenoids_settings_list[i]
        relay_status_dict[k] = solenoids_status_list[i]
        
    if emit:
        socketio.emit(
            "relay_status_updated", 
            {
                "relay_setting": relay_settings_dict,
                "relay_status": relay_status_dict
            }, 
            namespace="/manual"
        )

    return relay_settings_dict, relay_status_dict

@socketio.on("activateRelay", namespace="/manual")
def activateRelay(message):
    if message in config_dict["mks"]["relays"].keys():
        relay_num = config_dict["mks"]["relays"][message]["relay_num"]
        mks.set_relay_mode(relay_num, "SET")
    elif message in config_dict["mks"]["solenoids"]:
        mks_solenoids.activate_relay(config_dict["mks"]["solenoids"].index(message))
    time.sleep(0.1)
    get_relay_status(emit=True)

@socketio.on("deactivateRelay", namespace="/manual")
def deactivateRelay(message):
    if message in config_dict["mks"]["relays"].keys():
        relay_num = config_dict["mks"]["relays"][message]["relay_num"]
        mks.set_relay_mode(relay_num, "CLEAR")
    elif message in config_dict["mks"]["solenoids"]:
        mks_solenoids.deactivate_relay(config_dict["mks"]["solenoids"].index(message))
    time.sleep(0.1)
    get_relay_status(emit=True)