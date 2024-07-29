import logging

from printer_server.threading_wrapper import Thread
from printer_server.views.manual_controls import update_le_led_state
from printer_server.printer_control.screen_control import ScreenControl
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def getLightEngineFromJSON(light_engine):
    for engine in config_dict["light_engines"]:
        if engine in light_engine:
            return engine

def getLEDFromJSON(light_engine):
    led = 0
    _light_engine = getLightEngineFromJSON(light_engine)
    if len(config_dict[_light_engine]["leds"]) > 1:
        for i, wavelength in enumerate(config_dict[_light_engine]["leds"]):
            if wavelength in light_engine:
                led = i
                break
    return led

class LightEngineControl(ScreenControl):
    def __init__(self):
        super().__init__()
        self.light_engines = driver_handles.light_engines
        self.light_engine_threads = {}

    def connect_hardware(self):
        for light_engine, light_engine_driver in self.light_engines.items():
            thread = Thread(log, name=f"{light_engine}_control_connect_thread", target=light_engine_driver.connect, args=[self.shutdown])
            thread.start()
            self.light_engine_threads[light_engine] = thread
        super().connect_hardware()
        for light_engine, thread in self.light_engine_threads.items():
            thread.join()
            if not self.light_engines[light_engine].connected:
                log.error("%s failed to connect!", light_engine.capitalize())
                self.all_hardware_connected = False
        self.light_engine_threads = {}

    def initialize_hardware(self):
        for light_engine, light_engine_driver in self.light_engines.items():
            thread = Thread(log, name=f"{light_engine}_control_init_thread", target=light_engine_driver.initialize, args=[])
            thread.start()
            self.light_engine_threads[light_engine] = thread
        super().initialize_hardware()
        for light_engine, thread in self.light_engine_threads.items():
            thread.join()
        self.light_engine_threads = {}

    def print_worker(self):
        if self.state != "printing":
            return
        if "visitech" in self.light_engines.keys():
            # clear visitech overcurrent error
            self.light_engines["visitech"].get_sticky_errors(warn="NONE")
            self.light_engines["visitech"].suppress_ocp_error = True
        super().print_worker()

    def pre_exposure_tasks(self, settings, light_engine):
        _light_engine = getLightEngineFromJSON(light_engine)
        light_engine_driver = self.light_engines[_light_engine]
        
        self.light_engine_threads = Thread(
            log, 
            name=f"{_light_engine}_control_setup_thread",
            target=light_engine_driver.setup_exposure,
            args=[self.exposure_time_ms, self.power],
            kwargs={"led_num": getLEDFromJSON(light_engine)},
        )
        self.light_engine_threads.start()
        super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, light_engine):
        self.light_engine_threads.join()
        return super().pre_exposure_joins(light_engine)

    def exposure(self, settings, light_engine):
        _light_engine = getLightEngineFromJSON(light_engine)
        light_engine_driver = self.light_engines[_light_engine]
        update_le_led_state(_light_engine, True)
        light_engine_driver.perform_exposure()
        update_le_led_state(_light_engine, False)
        super().exposure(settings, light_engine)

    def get_le_status(self, settings, light_engine, warn="ALL"):
        _light_engine = getLightEngineFromJSON(light_engine)
        light_engine_driver = self.light_engines[_light_engine]
        return light_engine_driver.read_all_status(warn)
    
    def post_print_tasks(self):
        super().post_print_tasks()
        # always turn off the light engines
        for light_engine, light_engine_driver in self.light_engines.items():
            light_engine_driver.stop_sequencer()
            update_le_led_state(light_engine, False)