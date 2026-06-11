import logging

from printer_server.threading_wrapper import Thread
from printer_server.hardware_configuration.hardware_configuration import driver_handles
from printer_server.printer_control.print_control import PrintControl, run_in_thread

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class GPIOControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.gpio = driver_handles.gpio

    def initialize_hardware(self):
        gpio_thread = Thread(log, name="gpio_control_init_thread", target=self.gpio.initialize, args=[self.shutdown])
        gpio_thread.start()
        super().initialize_hardware()
        gpio_thread.join()
        if gpio_thread.exception is not None:
            log.error("GPIO failed to connect!")
            self.failed_hardware["GPIO"] = self.gpio


class FilmGPIOControl(GPIOControl):
    def move_build_platform_up(self, position_settings):
        try:
            self.gpio.film_relay_on()
        except Exception as ex:
            log.warning("Unable to activate film relay (%s)", ex, exc_info=True)
        super().move_build_platform_up(position_settings)
        try:
            self.gpio.film_relay_off()
        except Exception as ex:
            log.warning("Unable to deactivate film relay (%s)", ex, exc_info=True)

class WintechFanGPIOControl(GPIOControl):
    def pre_exposure_tasks(self, settings, light_engine):
        """Move X, Y, and Focus stages to exposure positions"""
        le = self.convert_json_le_to_le(light_engine)

        if le == "wintech":
            try:
                self.gpio.wintech_fan_relay_on()
            except Exception as ex:
                log.warning("Unable to activate wintech fan relay (%s)", ex, exc_info=True)
        else:
            try:
                self.gpio.wintech_fan_relay_off()
            except Exception as ex:
                log.warning("Unable to deactivate wintech fan relay (%s)", ex, exc_info=True)

        super().pre_exposure_tasks(settings, light_engine)

    def post_print_tasks(self):
        super().post_print_tasks()
        try:
            self.gpio.wintech_fan_relay_off()
        except Exception as ex:
            log.warning("Unable to deactivate wintech fan relay (%s)", ex, exc_info=True)