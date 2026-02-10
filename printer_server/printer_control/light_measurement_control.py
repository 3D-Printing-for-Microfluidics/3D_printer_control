import os
import time
import logging
from datetime import datetime

import printer_server.views.home as home
from printer_server.settings import Config
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.printer_control.print_control import PrintControl, run_in_thread
from printer_server.views.manual_controls import update_le_led_state, update_screen_preview
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class LightMeasurementControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.spectrometer = driver_handles.spectrometer
        self.light_engines = driver_handles.light_engines
        self.photodiode = driver_handles.photodiode

    def connect_hardware(self):
        # Connect spectrometer and photodiode 
        spectrometer_thread = Thread(log, name="spectrometer_connect_thread", target=self.spectrometer.connect)
        photodiode_thread = Thread(log, name="photodiode_connect_thread", target=self.photodiode.connect)
        spectrometer_thread.start()
        photodiode_thread.start()
        super().connect_hardware()
        spectrometer_thread.join()
        photodiode_thread.join()
        if not self.spectrometer.connected or spectrometer_thread.exception is not None:
            log.error("Spectrometer failed to connect!")
            self.failed_hardware["Spectrometer"] = self.spectrometer   
        if not self.photodiode.connected or photodiode_thread.exception is not None:
            log.error("Photodiode failed to connect!")
            self.failed_hardware["Photodiode"] = self.photodiode

    def initialize_hardware(self):
        photodiode_thread = Thread(log, name="photodiode_init_thread", target=self.photodiode.initialize, args=[])
        photodiode_thread.start()
        super().initialize_hardware()
        if photodiode_thread is not None:
            photodiode_thread.join()
            if photodiode_thread.exception is not None:
                log.error("Photodiode failed to initialize!")
                self.failed_hardware["Photodiode"] = self.photodiode

    def pre_print_tasks(self):
        super().pre_print_tasks()
        if not self.printing_paused.is_set():
            try:
                self.measure_light("preprint")
            except Exception as ex:
                log.warning("Error occured during light measurement (%s)", ex, exc_info=True)

    def post_print_tasks(self):
        if not (self.printing_stopped.is_set() or self.printing_paused.is_set()):
            try:
                self.measure_light("postprint")
            except Exception as ex:
                log.warning("Error occured during light measurement (%s)", ex, exc_info=True)
        super().post_print_tasks()

    def measure_light(self, path_prefix):
        for light_engine in config_dict["light_engines"]:
            
            # Move x/y/focus to spectrometer location
            x_pos = self.coord_systems[f"fiber_{light_engine}"]["X"]
            y_pos = self.coord_systems[f"fiber_{light_engine}"]["Y"]
            focus_pos = self.coord_systems[f"fiber_{light_engine}"]["Focus"]
            self.xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False)
            self.focus_thread = self.focus_stage.threadedFocusMove(log, focus_pos, join=False)

            # Join threads
            for thread in self.xy_threads:
                if thread is not None:
                    thread.join()
                    if thread.exception is not None:
                        raise thread.exception
            if self.focus_thread is not None:
                self.focus_thread.join()
                if self.focus_thread.exception is not None:
                    raise self.focus_thread.exception

            # Setup light engines
            for i, wavelength in enumerate(config_dict[light_engine]["leds_nm"]):
                light_engine_driver = self.light_engines[light_engine]
                num_avg = config_dict["spectrometer"]["default_number_of_averages"]

                try:
                    self.screen.setCorrectionEnable(False, light_engine=light_engine)
                except:
                    continue

                light_engine_thread = Thread(
                    log, 
                    name=f"{light_engine}_control_setup_thread",
                    target=light_engine_driver.setup_exposure,
                    args=[10000],
                    kwargs={"led_power": 100, "repeat": 0, "is_grayscale_corrected":False, "led_num": i},
                )

                imagePath = os.path.join(
                    Config.PRINT_SERVER_FOLDER, f"drivers/{light_engine}/images", f"white.png"
                )
                print(imagePath, light_engine)
                screen_thread = Thread(
                    log, name="screen_control_draw_thread", target=self.screen.draw, args=[imagePath], kwargs={"light_engine": light_engine, "led_num": i}
                )
                light_engine_thread.start()
                screen_thread.start()

                light_engine_thread.join()
                if light_engine_thread.exception is not None:
                    raise light_engine_thread.exception
                self.screen_thread.join()
                if self.screen_thread.exception is not None:
                    raise self.screen_thread.exception

                # Turn on light engine
                update_le_led_state(light_engine, True)
                light_engine_driver.perform_exposure()
                time.sleep(0.1)

                update_screen_preview(
                    light_engine, 
                    self.screen.fetch_preview(light_engine)
                )

                # Measure spectrum and irradiance
                try:
                    integration_time, spectrum = self.measure_spectra(num_avg)
                except:
                    log.warning("Unable to measure spectra")
                try:
                    irr1 = self.measure_irradiance(wavelength)
                except:
                    log.warning("Unable to measure irradiance")

                # Turn off light engine
                light_engine_driver.stop_sequencer()
                update_le_led_state(light_engine, False)

                try:
                    self.screen.setCorrectionEnable(True, light_engine=light_engine)
                except Exception as ex:
                    continue

                light_engine_thread = Thread(
                    log, 
                    name=f"{light_engine}_control_setup_thread",
                    target=light_engine_driver.setup_exposure,
                    args=[10000],
                    kwargs={"led_power": 100, "repeat": 0, "is_grayscale_corrected":True, "led_num": i},
                )

                light_engine_thread.start()
  
                light_engine_thread.join()
                if light_engine_thread.exception is not None:
                    raise light_engine_thread.exception

                # Turn on light engine
                update_le_led_state(light_engine, True)
                light_engine_driver.perform_exposure()
                time.sleep(0.1)

                update_screen_preview(
                    light_engine, 
                    self.screen.fetch_preview(light_engine)
                )

                try:
                    irr2 = self.measure_irradiance(wavelength)
                except:
                    log.warning("Unable to measure irradiance")  

                
                # Turn off light engine
                light_engine_driver.stop_sequencer()
                update_le_led_state(light_engine, False)

                # Save spectrum to file
                spectra_path = str(self.current_job / "logs" / f"{path_prefix}_spectra_{light_engine}_{wavelength}_nm.csv")
                async_file_hander.write(spectra_path, f"Wavelength: {wavelength} (nm)\n")
                async_file_hander.write(spectra_path, f"Irradiance: {irr1} mW/cm^2\n")     
                async_file_hander.write(spectra_path, f"Irradiance (grayscale corrected): {irr2} mW/cm^2\n")               
                async_file_hander.write(spectra_path, f"Integration time: {integration_time} ms\n")
                async_file_hander.write(spectra_path, f"Number of Averages: {num_avg}\n")
                async_file_hander.write(spectra_path, "\n")
                if spectrum is not None:
                    async_file_hander.write(spectra_path, "wavelength (nm),counts\n")
                    for _wavelength, _counts in zip(spectrum[0], spectrum[1]):
                        async_file_hander.write(spectra_path, f"{_wavelength},{_counts}\n") 
                    
    def measure_spectra(self, avg=1):
            log.info("Calculating spectrometer integration time")
            integration_time = self.spectrometer.set_integration_time(None)
            log.info("Measuring spectra")
            return integration_time, self.spectrometer.get_spectrum(avg)
            
    def measure_irradiance(self, l):
            log.info("Setting wavelength for irradiance")
            self.photodiode.set_wavelength(l)
            log.info("Measuring irradiance")   
            irradiances = []
            for _ in range(100):
                irradiances.append(self.photodiode.get_power_density())
                time.sleep(0.01)
            log.info("Irradiance is %.2f mW/cm^2", sum(irradiances)/len(irradiances))
            return sum(irradiances)/len(irradiances)