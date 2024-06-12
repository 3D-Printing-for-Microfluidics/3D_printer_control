# socket.on("relay_status_updated", function (message) {
#     pumpSetting = message["relay_setting"]["vacuum_pump"];
#     valveSetting = {
#         valve_pump1: message["relay_setting"]["valve_pump1"],
#         valve_vent1: message["relay_setting"]["valve_vent1"],
#         valve_pump2: message["relay_setting"]["valve_pump2"],
#         valve_vent2: message["relay_setting"]["valve_vent2"],
#         valve_vacuum: message["relay_setting"]["valve_vacuum"],
#     };
#     valveStatus = {
#         valve_pump1: message["relay_status"]["valve_pump1"],
#         valve_vent1: message["relay_status"]["valve_vent1"],
#         valve_pump2: message["relay_status"]["valve_pump2"],
#         valve_vent2: message["relay_status"]["valve_vent2"],
#         valve_vacuum: message["relay_status"]["valve_vacuum"],
#     };
# });

# socket.on("pressure_readings_updated", function (message) {
#     gaugeReading1 = message["gauge"][0];
#     gaugeReading2 = message["gauge"][1];
#     updateChamberStatus();
# });

# socket.emit("activateRelay", "");
# socket.emit("deactivateRelay", "");
# "vacuum_pump"
# "valve_pump1"
# "valve_vent1"
# "valve_pump2"
# "valve_vent2"
# "valve_vacuum"

import time
import logging
from printer_server.extensions import socketio
from printer_server.threading_wrapper import Thread
from printer_server.hardware_configuration import driver_handles, config_dict
from flask import request

mks = driver_handles.mks
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
    relay_settings_dict = {}
    for i, v in enumerate(config_dict["mks"]["relays"]):
        relay_settings_dict[v] = relay_settings_list[i]

    if emit:
        socketio.emit(
            "relay_status_updated", 
            {
                "relay_setting": relay_settings_dict,
                "relay_status": relay_settings_dict
            }, 
            namespace="/manual"
        )

    return relay_settings_dict, relay_settings_dict

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
    mks.set_relay_mode(config_dict["mks"]["relays"].index(message), "SET")
    time.sleep(1)
    get_relay_status(emit=True)

@socketio.on("deactivateRelay", namespace="/manual")
def deactivateRelay(message):
    mks.set_relay_mode(config_dict["mks"]["relays"].index(message), "CLEAR")
    time.sleep(1)
    get_relay_status(emit=True)