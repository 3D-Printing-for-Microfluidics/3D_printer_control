import logging

from printer_server.threading_wrapper import Thread
from printer_server.hardware_configuration import driver_handles
from printer_server.printer_control.print_control import PrintControl

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class GPIOControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.gpio = driver_handles.gpio

    def initialize_hardware(self):
        gpio_thread = Thread(log, name="gpio_control_init_thread", target=self.gpio.initialize, args=[])
        gpio_thread.start()
        super().initialize_hardware()
        gpio_thread.join()


class FilmGPIOControl(GPIOControl):
    def move_build_platform_up(self, position_settings):
        self.gpio.film_relay_on()
        super().move_build_platform_up(position_settings)
        self.gpio.film_relay_off()