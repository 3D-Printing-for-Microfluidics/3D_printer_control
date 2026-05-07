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
        # else:
        #     import os
        #     from printer_server.settings import Config
        #     print_server = Config.PRINT_SERVER_FOLDER
        #     for i, light_engine in enumerate(self.screen.light_engines):
        #         imagePath = os.path.join(
        #             print_server, "drivers", light_engine, "images", f"{light_engine}_{i+1}.png"
        #         )
        #         self.screen.draw(imagePath, light_engine=light_engine, led_num=0)

    def pre_exposure_tasks(self, settings, light_engine):
        from printer_server.printer_control.light_engine_control import parseJSONLightEngine
        le, led = parseJSONLightEngine(light_engine, settings.get("Light engine wavelength (nm)"))

        # "Do light grayscale correction" setting deprecated, use "Do grayscale correction"
        corrected = settings.get(
            "Do light grayscale correction",
            settings.get("Do grayscale correction", False),
        )
        self.screen.setCorrectionEnable(corrected, light_engine=le)

        mirror_short = settings.get("Mirror image short axis", False)
        mirror_long = settings.get("Mirror image long axis", False)

        self.screen_thread = Thread(
            log, 
            name="screen_control_draw_thread", 
            target=self.screen.draw, 
            args=[self.image], 
            kwargs={
                "light_engine": le, 
                "led_num": led, 
                "mirror_short": mirror_short, 
                "mirror_long": mirror_long
            }
        )
        self.screen_thread.start()
        super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, light_engine):
        from printer_server.printer_control.light_engine_control import parseJSONLightEngine
        le, led = parseJSONLightEngine(light_engine)
        self.screen_thread.join()
        if self.screen_thread.exception is not None:
            log.critical("Unable draw to screen")
            self.failed_hardware["Virtual Screen"] = self.screen
            raise PrintingException()
        update_screen_preview(
            le, 
            self.screen.fetch_preview(le)
        )
        return super().pre_exposure_joins(light_engine)
    
    def screen_post_print_tasks(self):
        for le in self.screen.light_engines:
            try:
                self.screen.clear(le)
                self.screen.setCorrectionEnable(False, light_engine=le)
                update_screen_preview(
                    le, 
                    self.screen.fetch_preview(le)
                )
            except Exception as ex:
                log.critical("Unable clear screen (%s)", ex, exc_info=True)
                self.failed_hardware["Virtual Screen"] = self.screen
                raise PrintingException()
    
    def post_print_tasks(self):
        super().post_print_tasks()
        self.screen_thread = Thread(log, name="screen_control_draw_thread", target=self.screen_post_print_tasks)
        self.screen_thread.start()

    def post_print_joins(self):
        if self.screen_thread is not None:
            self.screen_thread.join()
        return super().post_print_joins()