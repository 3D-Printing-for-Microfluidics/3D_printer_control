import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict

light_engines = driver_handles.light_engines

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

@socketio.on("light_engine_stop", namespace="/manual")
def light_engine_stop(light_engine):
    """Turn off the LED in the light engine."""
    try:
        light_engines[light_engine].stop_sequencer()
        light_engines[light_engine].idle_on()
        socketio.emit("light_engine_update_led_state", {"light_engine":light_engine, "state":False}, namespace="/manual")
        socketio.emit("light_engine_done", namespace="/manual")
    except Exception as ex:
        log.warn("%s manual control failed (%s)", light_engine.capitalize(), ex, exc_info=True)
        socketio.emit("hardware_failure", light_engine, namespace="/manual")


@socketio.on("light_engine_start", namespace="/manual")
def light_engine_start(message):
    """Project the image with the given settings."""
    try:
        light_engine = message["light_engine"]
        ledPower = int(message["ledPower"])
        repeat = int(message["repeat"])
        exposure = int(message["exposure"])
        led = int(message.get("led", 0))
        socketio.emit("light_engine_update_led_state", {"light_engine":light_engine, "state":True}, namespace="/manual")
        light_engines[light_engine].idle_off()
        light_engines[light_engine].stop_sequencer()
        light_engines[light_engine].setup_exposure(exposure, led_power=ledPower, repeat=repeat, led_num=led)
        light_engines[light_engine].perform_exposure()
        if repeat != 0:
            socketio.emit("light_engine_update_led_state", {"light_engine":light_engine, "state":False}, namespace="/manual")
            light_engines[light_engine].idle_on()
        socketio.emit("light_engine_done", namespace="/manual")
    except Exception as ex:
        log.warn("%s manual control failed (%s)", light_engine.capitalize(), ex, exc_info=True)
        socketio.emit("hardware_failure", light_engine, namespace="/manual")


@socketio.on("light_engine_get_status", namespace="/manual")
def light_engine_get_status(light_engine):
    try:
        socketio.emit(
            "light_engine_return_status",
            light_engines[light_engine].read_all_status(warn="ALL"),
            namespace="/manual"
        )
    except Exception as ex:
        log.warn("%s manual control failed (%s)", light_engine.capitalize(), ex, exc_info=True)
        socketio.emit("hardware_failure", light_engine, namespace="/manual")

def getLedStatus(emit=True):
    for light_engine in config_dict["light_engines"]:
        try:
            state = light_engines[light_engine].get_led_status()
            if emit:
                socketio.emit(f"light_engine_update_led_state", {"light_engine": light_engine, "state":state}, namespace="/manual")
        except Exception as ex:
            log.warn("%s manual control failed (%s)", light_engine.capitalize(), ex, exc_info=True)
            socketio.emit("hardware_failure", light_engine, namespace="/manual")