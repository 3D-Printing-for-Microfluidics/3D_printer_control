from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles

light_engines = driver_handles.light_engines


@socketio.on("light_engine_stop", namespace="/manual")
def light_engine_stop(light_engine):
    """Turn off the LED in the light engine."""
    light_engines[light_engine].stop_sequencer()
    socketio.emit("light_engine_update_led_state", {"light_engine":light_engine, "status":False}, namespace="/manual")
    socketio.emit("light_engine_done", namespace="/manual")


@socketio.on("light_engine_start", namespace="/manual")
def light_engine_start(message):
    """Project the image with the given settings."""
    light_engine = message["light_engine"]
    ledPower = int(message["ledPower"])
    repeat = int(message["repeat"])
    exposure = int(message["exposure"])
    led = int(message.get("led", 0))
    socketio.emit("light_engine_update_led_state", {"light_engine":light_engine, "status":True}, namespace="/manual")
    light_engines[light_engine].setup_exposure(exposure, led_power=ledPower, repeat=repeat, led_num=led)
    light_engines[light_engine].perform_exposure()
    if repeat != 0:
        socketio.emit("light_engine_update_led_state", {"light_engine":light_engine, "status":False}, namespace="/manual")
    socketio.emit("light_engine_done", namespace="/manual")


@socketio.on("light_engine_get_status", namespace="/manual")
def light_engine_get_status(light_engine):
    socketio.emit(
        "light_engine_return_status",
        light_engines[light_engine].read_all_status(warn="ALL"),
        namespace="/manual"
    )


def getLedStatus(light_engine):
    return light_engines[light_engine].get_led_status()
