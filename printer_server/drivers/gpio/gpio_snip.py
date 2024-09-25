import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles

gpio = driver_handles.gpio

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

@socketio.on("gpio_switch_film_relay", namespace="/manual")
def setFilmRelayState(message):
    try:
        if message == "On":
            gpio.film_relay_on()
        else:
            gpio.film_relay_off()
    except Exception as ex:
        log.warn("GPIO manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "gpio", namespace="/manual")

def getFilmRelayState(emit=True):
    try:
        if emit:
            socketio.emit("gpio_film_relay_state", gpio.film_relay_state, namespace="/manual")
        return gpio.film_relay_state
    except Exception as ex:
        log.warn("GPIO manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "xy", namespace="/manual")
        return False