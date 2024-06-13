import time
import logging
from printer_server.extensions import socketio
from printer_server.threading_wrapper import Thread
from printer_server.hardware_configuration import driver_handles, config_dict
from flask import request

mks = driver_handles.mks
mks_solenoids = driver_handles.mks_solenoids
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def get_gauges(emit=False):
    gauges = [mks.read_pressure(1), mks.read_pressure(2)]
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
    for k, v in enumerate(config_dict["mks"]["relays"]):
        relay_settings_dict[k] = relay_settings_list[v["relay_num"]]

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

mks_running = False
def mks_loop():
    while mks_running:
        get_relay_status(emit=True)
        get_gauges(emit=True)
        time.sleep(10)

mks_thread = Thread(log, name="mks_poll_thread", target=mks_loop)
mks_running = True
mks_thread.start()

# @socketio.on("connecting", namespace="/manual")
# def connecting():
#     if not mks_running:
#         mks_running = True
#         mks_thread.start()


# @socketio.on("disconnect", namespace="/manual")
# def disconnect():
#     if mks_running:
#         mks_running = False
#         mks_thread.join()
#         mks_thread = Thread(log, name="mks_poll_thread", target=mks_loop)
#     log.debug("Socket disconnected %s", request.sid)


@socketio.on("activateRelay", namespace="/manual")
def activateRelay(message):
    relay_num = config_dict["mks"]["relays"][message]["relay_num"]
    if message in config_dict["mks"]["relays"].keys():
        mks.set_relay_mode(relay_num, "SET")
    elif message in config_dict["mks"]["solenoids"]:
        mks_solenoids.activate_relay(relay_num)
    time.sleep(0.1)
    get_relay_status(emit=True)

@socketio.on("deactivateRelay", namespace="/manual")
def deactivateRelay(message):
    relay_num = config_dict["mks"]["relays"][message]["relay_num"]
    if message in config_dict["mks"]["relays"].keys():
        mks.set_relay_mode(relay_num, "CLEAR")
    elif message in config_dict["mks"]["solenoids"]:
        mks_solenoids.deactivate_relay(relay_num)
    time.sleep(0.1)
    get_relay_status(emit=True)