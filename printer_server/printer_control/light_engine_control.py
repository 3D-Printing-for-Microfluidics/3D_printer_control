import os
import time
import logging

from printer_server.settings import Config
from printer_server.threading_wrapper import Thread
from printer_server.views.manual_controls import update_le_led_state
from printer_server.printer_control.print_control import PrintControl, PrintingException
from printer_server.views.manual_controls import update_light_engine_preview
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def parseJSONLightEngine(json_le, wavelength_nm=None):
    led = 0
    for le in config_dict["light_engines"]:
        if le in json_le:
            if len(config_dict[le]["leds_nm"]) > 1:
                if wavelength_nm is not None and wavelength_nm in config_dict[le]["leds_nm"]:
                    led = config_dict[le]["leds_nm"].index(wavelength_nm)
                else:
                    for i, wavelength in enumerate(config_dict[le]["leds_nm"]):
                        if str(wavelength) in json_le:
                            led = i
                            break
            return le, led

class LightEngineControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.light_engines = driver_handles.light_engines
        self.light_engine_threads = {}
        self.screen_thread = None

    def connect_hardware(self):
        for light_engine, light_engine_driver in self.light_engines.items():
            if light_engine_driver.config_dict["virtual_screen"]:
                if self.screen_thread is None:
                    screen_thread = Thread(log, name=f"{light_engine}_screen_connect_thread", target=light_engine_driver.screen.start, args=[])
                    screen_thread.start()
                    self.screen_thread = screen_thread
            thread = Thread(log, name=f"{light_engine}_control_connect_thread", target=light_engine_driver.connect)
            thread.start()
            self.light_engine_threads[light_engine] = thread
        super().connect_hardware()
        if self.screen_thread is not None:
            self.screen_thread.join()
            if self.screen_thread.exception is not None:
                log.error("Virtual Screen failed to connect!")
                self.failed_hardware[f"{light_engine.capitalize()} Light Engine"] = self.light_engines[light_engine]
        for light_engine, thread in self.light_engine_threads.items():
            thread.join()
            if not self.light_engines[light_engine].connected or thread.exception is not None:
                log.error("%s failed to connect!", light_engine.capitalize())
                self.failed_hardware[f"{light_engine.capitalize()} Light Engine"] = self.light_engines[light_engine]
        self.light_engine_threads = {}

    def initialize_hardware(self):
        for light_engine, light_engine_driver in self.light_engines.items():
            thread = Thread(log, name=f"{light_engine}_control_init_thread", target=light_engine_driver.initialize, args=[])
            thread.start()
            self.light_engine_threads[light_engine] = thread
        super().initialize_hardware()
        for light_engine, thread in self.light_engine_threads.items():
            thread.join()
            light_engine_driver = self.light_engines[light_engine]
            # if light_engine_driver.hdmi_reset and len(self.light_engines) > 1:
            #     if light_engine_driver.config_dict["virtual_screen"]:
            #         time.sleep(10)  # wait for light engine to come back after HDMI reset
            #         light_engine_driver.screen.stop(restart=True)
            #     light_engine_driver.hdmi_reset = False
            if thread.exception is not None:
                log.error("%s failed to initialize!", light_engine.capitalize())
                self.failed_hardware[f"{light_engine.capitalize()} Light Engine"] = self.light_engines[light_engine]
        self.light_engine_threads = {}

    def print_worker(self):
        if self.state != "printing":
            return
        if "visitech" in self.light_engines.keys():
            # clear visitech overcurrent error
            try:
                self.light_engines["visitech"].get_sticky_errors(warn="NONE")
                self.light_engines["visitech"].suppress_ocp_error = True
            except Exception as ex:
                log.critical("Unable communicate with light engine (%s)", ex, exc_info=True)
                self.failed_hardware[f"Visitech Light Engine"] = self.light_engines["visitech"]
                raise PrintingException()
        super().print_worker()

    def pre_print_tasks(self):
        for light_engine, light_engine_driver in self.light_engines.items():
            try:
                light_engine_driver.idle_off()
            except Exception as ex:
                log.critical("Unable communicate with light engine (%s)", ex, exc_info=True)
                self.failed_hardware[f"{light_engine.capitalize()} Light Engine"] = light_engine_driver
                raise PrintingException()
        super().pre_print_tasks()

    def pre_exposure_tasks(self, settings, light_engine):
        le, led = parseJSONLightEngine(light_engine, settings.get("Light engine wavelength (nm)"))
        light_engine_driver = self.light_engines[le]
        
        correction_images = light_engine_driver.config_dict.get("grayscale_correction_image", [])
        grayscale_available = len(correction_images) > led and correction_images.get(led, None) is not None

        # "Do light grayscale correction" setting deprecated, use "Do grayscale correction"
        corrected = settings.get(
            "Do light grayscale correction",
            settings.get("Do grayscale correction", grayscale_available),
        )

        mirror_short = settings.get("Mirror image short axis", False)
        mirror_long = settings.get("Mirror image long axis", False)

        self.screen_thread = Thread(
            log, 
            name=f"{light_engine}_control_draw_thread", 
            target=light_engine_driver.set_image, 
            args=[self.image], 
            kwargs={
                "led_num": led, 
                "grayscale_corrected": corrected,
                "mirror_short": mirror_short, 
                "mirror_long": mirror_long
            }
        )

        self.light_engine_threads = Thread(
            log, 
            name=f"{le}_control_setup_thread",
            target=light_engine_driver.setup_exposure,
            args=[self.exposure_time_ms],
            kwargs={"led_power": self.power, "led_num": led},
        )

        self.screen_thread.start()
        self.light_engine_threads.start()
        super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, light_engine):
        self.light_engine_threads.join()
        if self.light_engine_threads.exception is not None:
            log.critical("Unable communicate with light engine")
            self.failed_hardware[f"{light_engine.capitalize()} Light Engine"] = self.light_engines[light_engine]
            raise PrintingException()
        
        le, led = parseJSONLightEngine(light_engine)
        self.screen_thread.join()
        if self.screen_thread.exception is not None:
            log.critical("Unable draw to screen")
            self.failed_hardware[f"{light_engine.capitalize()} Light Engine"] = self.light_engines[light_engine]
            raise PrintingException()
        update_light_engine_preview(
            light_engine, 
            self.light_engines[le].get_image_preview()
        )
        return super().pre_exposure_joins(light_engine)

    def exposure(self, settings, light_engine):
        try:
            le, _ = parseJSONLightEngine(light_engine, settings.get("Light engine wavelength (nm)"))
            light_engine_driver = self.light_engines[le]
            update_le_led_state(le, True)
            light_engine_driver.perform_exposure()
            update_le_led_state(le, False)
        except Exception as ex:
            log.critical("Unable communicate with light engine (%s)", ex, exc_info=True)
            self.failed_hardware[f"{light_engine.capitalize()} Light Engine"] = light_engine_driver
            raise PrintingException()
        super().exposure(settings, light_engine)

    def get_le_status(self, settings, light_engine, warn="ALL"):
        try:
            le, _ = parseJSONLightEngine(light_engine, settings.get("Light engine wavelength (nm)"))
            light_engine_driver = self.light_engines[le]
            return light_engine_driver.read_all_status(warn)
        except Exception as ex:
            log.critical("Unable communicate with light engine (%s)", ex, exc_info=True)
            self.failed_hardware[f"{light_engine.capitalize()} Light Engine"] = light_engine_driver
            raise PrintingException()
        
    def le_post_print_tasks(self, light_engine, light_engine_driver):
        # always turn off the light engines
        try:
            light_engine_driver.stop_sequencer()
            update_le_led_state(light_engine, False)
            light_engine_driver.idle_on()

            imagePath = os.path.join(
                Config.PRINT_SERVER_FOLDER, f"drivers/{light_engine}/images", f"black.png"
            )
            light_engine_driver.set_image(imagePath, led_num=0, grayscale_corrected=False)
            update_light_engine_preview(
                light_engine, 
                light_engine_driver.get_image_preview()
            )
        except Exception as ex:
            log.critical("Unable communicate with light engine (%s)", ex, exc_info=True)
            self.failed_hardware[f"{light_engine.capitalize()} Light Engine"] = light_engine_driver
            raise PrintingException()
    
    def post_print_tasks(self):
        super().post_print_tasks()
        self.light_engine_threads = {}
        for light_engine, light_engine_driver in self.light_engines.items():
            thread = Thread(log, name=f"{light_engine}_control_post_print_thread", target=self.le_post_print_tasks, args=[light_engine, light_engine_driver])
            thread.start()
            self.light_engine_threads[light_engine] = thread
            
    def post_print_joins(self):
        for _, thread in self.light_engine_threads.items():
            thread.join()
        self.light_engine_threads = {}
        return super().post_print_joins()