import logging

from printer_server.threading_wrapper import Thread
from printer_server.views.manual_controls import update_screen_preview
from printer_server.printer_control.print_control import PrintControl, PrintingException, run_in_thread
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class ScreenControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.screen = driver_handles.screen
        self.screen_thread = None

    def connect_hardware(self):
        self.screen_thread = Thread(
            log, name="screen_control_connect_thread", target=driver_handles.screen.start, args=[]
        )
        self.screen_thread.start()
        super().connect_hardware()
        self.screen_thread.join()
        if self.screen_thread.exception is not None:
            log.error("Virtual Screen failed to connect!")
            self.failed_hardware["Virtual Screen"] = self.screen

    def pre_exposure_tasks(self, settings, light_engine):
        screen_index = 0
        for i, le in enumerate(self.screen.light_engines):
            if le in light_engine:
                screen_index = i
                break

        self.screen_thread = Thread(
            log, name="screen_control_draw_thread", target=self.screen.draw, args=[self.image], kwargs={"screen": screen_index}
        )
        self.screen_thread.start()
        super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, light_engine):
        self.screen_thread.join()
        if self.screen_thread.exception is not None:
            log.critical("Unable draw to screen")
            self.failed_hardware["Virtual Screen"] = self.screen
            raise PrintingException()
        update_screen_preview(
            light_engine, 
            self.screen.fetch_preview(self.screen.getScreenNumber(light_engine))
        )
        return super().pre_exposure_joins(light_engine)
    
    def post_print_tasks(self):
        super().post_print_tasks()
        for i in range(len(self.screen.light_engines)):
            try:
                self.screen.clear(screen=i)
                update_screen_preview(
                    self.screen.light_engines[i], 
                    self.screen.fetch_preview(i)
                )
            except Exception as ex:
                log.critical("Unable draw to screen (%s)", ex, exc_info=True)
                self.failed_hardware["Virtual Screen"] = self.screen
                raise PrintingException()