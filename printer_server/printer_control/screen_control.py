from printer_server.printer_control.print_control import *


class ScreenControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.screen = driver_handles.screen
        self.screen_thread = None

    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        if self.state == "uninitialized":
            self.screen_thread = Thread(
                log, name="screen_control_init_thread", target=driver_handles.screen.start, args=[]
            )
            self.screen_thread.start()
            super().initialize(run_in_thread=run_in_thread)
            self.screen_thread.join()

    def post_print_tasks(self):
        for i in range(len(config_dict["screen"]["light_engines"])):
            self.screen.clear(screen=i)
        super().post_print_tasks()

    def pre_exposure_tasks(self, settings, light_engine):
        screen_index = 0
        for i, le in enumerate(config_dict["screen"]["light_engines"]):
            if le in light_engine:
                screen_index = i
                break

        self.screen_thread = Thread(
            log, name="screen_control_draw_thread", target=self.screen.draw, args=[self.image], kwargs={"screen": screen_index}
        )
        self.screen_thread.start()
        super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, settings, light_engine):
        self.screen_thread.join()
        super().pre_exposure_joins(settings, light_engine)
