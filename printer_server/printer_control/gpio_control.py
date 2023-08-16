from printer_server.printer_control.print_control import *


class GPIOControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.gpio = driver_handles.gpio

    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        if self.state == "uninitialized":
            gpio_thread = Thread(log, name="gpio_control_init_thread", target=self.gpio.initialize, args=[])
            gpio_thread.start()
            super().initialize(run_in_thread=run_in_thread)
            gpio_thread.join()


class FilmGPIOControl(GPIOControl):
    def move_build_platform_up(self, position_settings):
        self.gpio.film_relay_on()
        super().move_build_platform_up(position_settings)
        self.gpio.film_relay_off()


class VisitechFanGPIOControl(GPIOControl):
    def pre_print_tasks(self):
        self.gpio.fan_relay_on()
        super().pre_print_tasks()
        self.gpio.fan_relay_off()

    def post_print_tasks(self):
        # always turn off the Visitech
        self.gpio.fan_relay_off()
        super().post_print_tasks()

    def pre_exposure_tasks(self, settings, light_engine):
        if light_engine == "wintech":
            if self.gpio.fan_relay_state == False:
                self.gpio.fan_relay_on()
        else:
            if self.gpio.fan_relay_state == True:
                self.gpio.fan_relay_off()
        super().pre_exposure_tasks(settings, light_engine)
