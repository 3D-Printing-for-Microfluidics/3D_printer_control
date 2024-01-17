import logging

from printer_server.threading_wrapper import Thread
from printer_server.views.manual_controls import update_le_led_status
from printer_server.printer_control.screen_control import ScreenControl
from printer_server.hardware_configuration import config_dict, driver_handles


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class VisitechControl(ScreenControl):
    def __init__(self):
        super().__init__()
        self.visitech = driver_handles.visitech
        self.visitech_thread = None

    def connect_hardware(self):
        self.visitech_thread = Thread(log, name="visitech_control_connect_thread", target=self.visitech.connect, args=[self.shutdown])
        self.visitech_thread.start()
        super().connect_hardware()
        self.visitech_thread.join()
        if not self.visitech.connected:
            log.error("Visitech failed to connect!")
            self.all_hardware_connected = False

    def initalize_hardware(self):
        self.visitech_thread = Thread(log, name="visitech_control_init_thread", target=self.visitech.initalize, args=[])
        self.visitech_thread.start()
        super().initalize_hardware()
        self.visitech_thread.join()

    def post_print_tasks(self):
        # always turn off the Visitech
        self.visitech.stop_sequencer()
        update_le_led_status("visitech", False)
        super().post_print_tasks()

    def print_worker(self):
        if self.state != "printing":
            return
        # clear visitech overcurrent error
        self.visitech.get_sticky_errors(warn=False)
        self.visitech.suppress_ocp_error = True
        super().print_worker()

    def pre_exposure_tasks(self, settings, light_engine):
        if "visitech" in light_engine:
            led = 0
            if len(config_dict["visitech"]["leds"]) > 1:
                for i, wavelength in enumerate(config_dict["visitech"]["leds"]):
                    if wavelength in light_engine:
                        led = i
                        break

            # visitech setup thread
            self.visitech_thread = Thread(
                log, 
                name="visitech_control_setup_thread",
                target=self.visitech.setup_exposure,
                args=[self.exposure_time_ms, self.power],
                kwargs={"led_num": led},
            )
            self.visitech_thread.start()
        else:
            self.visitech.suppress_ocp_error = True
        super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, light_engine):
        if "visitech" in light_engine:
            self.visitech_thread.join()
        return super().pre_exposure_joins(light_engine)

    def exposure(self, settings, light_engine):
        if "visitech" in light_engine:
            update_le_led_status("visitech", True)
            self.visitech.perform_exposure()
            update_le_led_status("visitech", False)
        super().exposure(settings, light_engine)

    def get_le_status(self, settings, light_engine):
        if "visitech" in light_engine:
            return self.visitech.read_all_status()
        return super().get_le_status(settings, light_engine)