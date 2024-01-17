import logging

from printer_server.threading_wrapper import Thread
from printer_server.hardware_configuration import driver_handles
from printer_server.printer_control.screen_control import ScreenControl
from printer_server.views.manual_controls import (
    update_le_led_status,
)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class WintechControl(ScreenControl):
    def __init__(self):
        super().__init__()
        self.wintech = driver_handles.wintech
        self.wintech_thread = None

    def connect_hardware(self):
        self.wintech_thread = Thread(log, name="wintech_control_connect_thread", target=self.wintech.connect, args=[])
        self.wintech_thread.start()
        super().connect_hardware()
        self.wintech_thread.join()
        if not self.wintech.connected:
            log.error("Wintech failed to connect!")
            self.all_hardware_connected = False

    def initalize_hardware(self):
        self.wintech_thread = Thread(log, name="wintech_control_init_thread", target=self.wintech.initalize, args=[])
        self.wintech_thread.start()
        super().initalize_hardware()
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

    def pre_exposure_joins(self, light_engine):
        if "wintech" in light_engine:
            self.wintech_thread.join()
        return super().pre_exposure_joins(light_engine)

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
