from printer_server.views.manual_controls import update_le_led_status

from printer_server.printer_control.print_control import *
from printer_server.printer_control.screen_control import *


# def door_is_open(visitech_sticky_errors):
#     """Return true if the door is open, else return false."""
#     if "open" in visitech_sticky_errors.capitalize():
#         return True
#     return False


class VisitechControl(ScreenControl):
    def __init__(self):
        super().__init__()
        self.visitech = driver_handles.visitech
        self.visitech_thread = None

    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        if self.state == "uninitialized":
            self.visitech_thread = threading.Thread(target=self.visitech.connect, args=[])
            self.visitech_thread.start()
            super().initialize(run_in_thread=run_in_thread)
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
        self.suppress_visitech_ocp_error = True
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
            self.visitech_thread = threading.Thread(
                target=self.visitech.setup_exposure,
                args=[self.exposure_time_ms, self.power],
                kwargs={"led_num": led},
            )
            self.visitech_thread.start()
        super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, settings, light_engine):
        if "visitech" in light_engine:
            self.visitech_thread.join()
        super().pre_exposure_joins(settings, light_engine)

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

    def post_exposure_tasks(self, msg):
        # Suppress the first Visitech OCP error. This appears to always be
        # triggered on the first exposure of each print job. It would be better
        # to figure out why this happens in the hardware and fix it there.
        if self.suppress_visitech_ocp_error:
            self.suppress_visitech_ocp_error = False  # only do this once per print
            for e in self.visitech.get_sticky_errors(warn=False):
                if e and e.lower() != "led over current protection triggered":
                    log.warning("Visitech error: %s", e)  # report other errors
        return super().post_exposure_tasks(msg)
