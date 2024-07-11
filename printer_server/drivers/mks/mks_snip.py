import time
import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles, config_dict

mks = driver_handles.mks
mks_teensy = driver_handles.mks_teensy
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
    teensy_relay_settings_list = mks_teensy.get_all_relay_status()
    teensy_relay_status_list = mks_teensy.get_all_sensor_status()
    relay_settings_dict = {}
    relay_status_dict = {}
    for k, v in config_dict["mks"]["relays"].items():
        relay_settings_dict[k] = relay_settings_list[v["relay_num"]-1]

    for i, k in enumerate(config_dict["mks"]["teensy relays"]):
        relay_settings_dict[k] = teensy_relay_settings_list[i]
        relay_status_dict[k] = teensy_relay_status_list[i]
        
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
    elif message in config_dict["mks"]["teensy relays"]:
        mks_teensy.activate_relay(config_dict["mks"]["teensy relays"].index(message))
    time.sleep(0.1)
    get_relay_status(emit=True)

@socketio.on("deactivateRelay", namespace="/manual")
def deactivateRelay(message):
    if message in config_dict["mks"]["relays"].keys():
        relay_num = config_dict["mks"]["relays"][message]["relay_num"]
        mks.set_relay_mode(relay_num, "CLEAR")
    elif message in config_dict["mks"]["teensy relays"]:
        mks_teensy.deactivate_relay(config_dict["mks"]["teensy relays"].index(message))
    time.sleep(0.1)
    get_relay_status(emit=True)