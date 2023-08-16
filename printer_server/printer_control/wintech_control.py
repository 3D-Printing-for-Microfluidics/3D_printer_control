from printer_server.views.manual_controls import (
    update_le_led_status,
)

from printer_server.printer_control.print_control import *
from printer_server.printer_control.screen_control import *


class WintechControl(ScreenControl):
    def __init__(self):
        super().__init__()
        self.wintech = driver_handles.wintech
        self.wintech_thread = None

    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        if self.state == "uninitialized":
            self.wintech_thread = Thread(log, name="wintech_control_init_thread", target=self.wintech.connect, args=[])
            self.wintech_thread.start()
            super().initialize(run_in_thread=run_in_thread)
            self.wintech_thread.join()

    def post_print_tasks(self):
        # always turn off the Wintech
        self.wintech.stop_sequencer()
        update_le_led_status("wintech", False)
        super().post_print_tasks()

    def pre_exposure_tasks(self, settings, light_engine):
        if "wintech" in light_engine:
            # wintech setup thread
            self.wintech_thread = Thread(
                log, 
                name="wintech_control_setup_thread",
                target=self.wintech.setup_exposure,
                args=[self.exposure_time_ms, self.power],
            )
            self.wintech_thread.start()
        super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, settings, light_engine):
        if "wintech" in light_engine:
            self.wintech_thread.join()
        super().pre_exposure_joins(settings, light_engine)

    def exposure(self, settings, light_engine):
        if "wintech" in light_engine:
            update_le_led_status("wintech", True)
            self.wintech.perform_exposure()
            update_le_led_status("wintech", False)
        super().exposure(settings, light_engine)

    def get_le_status(self, settings, light_engine):
        if "wintech" in light_engine:
            return ""
        return super().get_le_status(settings, light_engine)
