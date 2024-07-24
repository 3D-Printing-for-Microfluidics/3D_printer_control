from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles

gpio = driver_handles.gpio

@socketio.on("gpio_switch_film_relay", namespace="/manual")
def setFilmRelayState(message):
    if message == "On":
        gpio.film_relay_on()
    else:
        gpio.film_relay_off()

def getFilmRelayState():
    return gpio.film_relay_state
