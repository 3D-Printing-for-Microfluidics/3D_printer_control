import time
import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict

mks = driver_handles.mks
mks_teensy = driver_handles.mks_teensy

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def load_mks():
    try:
        socketio.emit(
            "mks_load", {
                "target":config_dict["mks"]["target"], 
                "atm":config_dict["mks"]["atm pressure"]-50,
                "limits":f"{mks_teensy.get_crane_lower_limit()}, {mks_teensy.get_crane_upper_limit()}"
            }, namespace="/manual"
        )
    except Exception as ex:
        log.warn("MKS manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "mks", namespace="/manual")


def get_gauges(emit=True):
    try:
        gauges = mks.read_all_pressures()
        if emit:
            socketio.emit(
                "mks_update_pressure_readings", {"gauge":gauges}, namespace="/manual"
            )
        return gauges
    except Exception as ex:
        log.warn("MKS manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "mks", namespace="/manual")


def get_relay_status(emit=True):
    try:
        relay_settings_list = mks.get_all_relay_status()
        teensy_relay_settings_list = mks_teensy.get_all_relay_status()
        relay_settings_dict = {}
        for k, v in config_dict["mks"]["relays"].items():
            relay_settings_dict[k] = relay_settings_list[v["relay_num"]-1]

        for i, k in enumerate(config_dict["mks"]["teensy relays"]):
            relay_settings_dict[k] = teensy_relay_settings_list[i]
            
        if emit:
            socketio.emit(
                "mks_update_relay_status", 
                {
                    "relay_setting": relay_settings_dict
                }, 
                namespace="/manual"
            )

        return relay_settings_dict
    except Exception as ex:
        log.warn("MKS manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "mks", namespace="/manual")


@socketio.on("mks_switch_relay", namespace="/manual")
def switchRelay(message):
    try:
        if message["relay"] in config_dict["mks"]["relays"].keys():
            relay_num = config_dict["mks"]["relays"][message["relay"]]["relay_num"]
            if message["state"]:
                mks.set_relay_mode(relay_num, "SET")
            else:
                mks.set_relay_mode(relay_num, "CLEAR")
        elif message["relay"] in config_dict["mks"]["teensy relays"]:
            mks_teensy.switch_relay(config_dict["mks"]["teensy relays"].index(message["relay"]), message["state"])
        time.sleep(0.1)
        get_relay_status()
    except Exception as ex:
        log.warn("MKS manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "mks", namespace="/manual")


def cranePosition(emit=True):
    try:
        pos = mks_teensy.get_crane_position()
        if emit:
            socketio.emit("mks_crane_done", pos, namespace="/manual")
        return pos
    except Exception as ex:
        log.warn("MKS manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "mks", namespace="/manual")


@socketio.on("mks_crane_move", namespace="/manual")
def craneMove(message):
    try:
        if message["mm"] == "Top":
            pos = mks_teensy.move_crane_top()
        elif message["mm"] == "Bottom":
            pos = mks_teensy.move_crane_bottom()
        else:    
            distance_mm = float(message["mm"])
            mode = message["mode"]
            mode = (
                mode != "absolute"
            )  # convert mode to True/False, absolute is true, all else is false
            pos = mks_teensy.move_crane(distance_mm, relative=mode)
        socketio.emit("mks_crane_done", pos, namespace="/manual")
    except Exception as ex:
        log.warn("MKS manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "mks", namespace="/manual")


