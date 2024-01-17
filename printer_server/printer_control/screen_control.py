import logging

from printer_server.threading_wrapper import Thread
from printer_server.printer_control.print_control import PrintControl
from printer_server.hardware_configuration import config_dict, driver_handles

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class ScreenControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.screen = driver_handles.screen
        self.screen_thread = None

    def connect_hardware(self):
        self.screen_thread = Thread(
            log, name="screen_control_start_thread", target=driver_handles.screen.start, args=[]
        )
        self.screen_thread.start()
        super().connect_hardware()
        self.screen_thread.join()

    def post_print_tasks(self):
        for i in range(len(config_dict["screen"]["light_engines"])):
            self.screen.clear(screen=i)
        super().post_print_tasks()

    def pre_exposure_tasks(self, settings, light_engine):
        super().pre_exposure_tasks(settings, light_engine)
        screen_index = 0
        for i, le in enumerate(config_dict["screen"]["light_engines"]):
            if le in light_engine:
                screen_index = i
                break

        self.screen_thread = Thread(
            log, name="screen_control_draw_thread", target=self.screen.draw, args=[self.image], kwargs={"screen": screen_index}
        )
        self.screen_thread.start()

    def pre_exposure_joins(self, light_engine):
        self.screen_thread.join()
        return super().pre_exposure_joins(light_engine)
