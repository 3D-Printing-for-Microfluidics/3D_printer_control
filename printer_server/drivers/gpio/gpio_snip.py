from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles

gpio = driver_handles.gpio


@socketio.on("fan_relay_mode", namespace="/manual")
def setFanRelayState(message):
    if message == "On":
        gpio.fan_relay_on()
    else:
        gpio.fan_relay_off()


@socketio.on("film_relay_mode", namespace="/manual")
def setFilmRelayState(message):
    if message == "On":
        gpio.film_relay_on()
    else:
        gpio.film_relay_off()


def getFanRelayState():
    return gpio.fan_relay_state


def getFilmRelayState():
    return gpio.film_relay_state
