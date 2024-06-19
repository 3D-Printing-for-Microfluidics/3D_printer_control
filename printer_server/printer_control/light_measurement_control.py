import os
import time
import logging
from datetime import datetime

import printer_server.views.home as home
from printer_server.settings import Config
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.printer_control.print_control import PrintControl
from printer_server.views.manual_controls import update_le_led_status
from printer_server.hardware_configuration import config_dict, driver_handles

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class LightMeasurementControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.spectrometer = driver_handles.spectrometer
        self.light_engines = driver_handles.light_engines
        self.photodiode = driver_handles.photodiode

    def connect_hardware(self):
        # Connect spectrometer
        spectrometer_thread = Thread(log, name="spectrometer_setup_thread", target=self.spectrometer.connect, args=[])
        spectrometer_thread.start()
        super().connect_hardware()
        spectrometer_thread.join()
        if not self.spectrometer.connected:
            log.error("Spectrometer failed to connect!")
            self.all_hardware_connected = False
        
        # Connect photodiode    
        photodiode_thread = Thread(log, name="photodiode_setup_thread", target=self.photodiode.connect, args=[])
        photodiode_thread.start()
        super().connect_hardware()
        photodiode_thread.join()
        if not self.photodiode.connected:
            log.error("Photodiode failed to connect!")
            self.all_hardware_connected = False    

    def pre_print_tasks(self):
        super().pre_print_tasks()
        self.measure_light("preprint")

    def post_print_tasks(self):
        if not self.printing_stopped.is_set():
            self.measure_light("postprint")
        super().post_print_tasks()

    def measure_light(self, path_prefix):
        for light_engine in config_dict["light_engines"]:
            
            # Move x/y/focus to spectrometer location
            x_pos = self.coord_systems[f"fiber_{light_engine}"]["X"]
            y_pos = self.coord_systems[f"fiber_{light_engine}"]["Y"]
            focus_pos = self.coord_systems[f"fiber_{light_engine}"]["Focus"]
            self.xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False)
            self.focus_thread = self.focus_stage.threadedFocusMove(log, focus_pos, join=False)

            # Setup light engines
            for i, wavelength in enumerate(config_dict[light_engine]["leds"]):
                light_engine_driver = self.light_engines[light_engine]
                light_engine_thread = Thread(
                    log, 
                    name=f"{light_engine}_control_setup_thread",
                    target=light_engine_driver.setup_exposure,
                    args=[10000, 100],
                    kwargs={"repeat": 0, "led_num": i},
                )
                light_engine_thread.start()

                # Draw to screen
                imagePath = os.path.join(
                    Config.PRINT_SERVER_FOLDER, f"drivers/{light_engine}/images", f"white.png"
                )
                screen_index = 0
                for i, le in enumerate(self.screen.light_engines):
                    if le in light_engine:
                        screen_index = i
                        break

                screen_thread = Thread(
                    log, name="screen_control_draw_thread", target=self.screen.draw, args=[imagePath], kwargs={"screen": screen_index}
                )
                screen_thread.start()

                # Join threads
                for thread in self.xy_threads:
                    if thread is not None:
                        thread.join()
                if self.focus_thread is not None:
                    self.focus_thread.join()
                light_engine_thread.join()
                self.screen_thread.join()

                # Turn on light engine
                update_le_led_status(light_engine, True)
                light_engine_driver.perform_exposure()

                # Measure spectrum
                self.num_avg = config_dict["spectrometer"]["default_number_of_averages"]
                self.integration_time = None
                self.spectrum = None
                spectrum_thread = Thread(log, name="spectrum_measure_thread", target=self.measure_spectra, args = ())
                spectrum_thread.start()
                spectrum_thread.join()
                
                # ##### Collect photodiode power here 
                ##initialize, write, then save
                # Measure irradiance 
                self.default_wavelength=config_dict["photodiode"]["default_wavelength"] 
                self.irradiance = None   
                irradiance_thread = Thread(log, name="irradiance_measure_thread", target=self.measure_irradiance, args = ())
                irradiance_thread.start()
                irradiance_thread.join()    
    
                # Turn off light engine
                light_engine_driver.stop_sequencer()
                update_le_led_status(light_engine, False)

                # Save spectrum to file
                spectra_path = str(self.current_job / f"{path_prefix}_spectra_{light_engine}_{wavelength}.csv")
                # async_file_hander.write(spectra_path, "HEADER INFORMATION...\n")
                                
                async_file_hander.write(spectra_path, f"Integration time: {self.integration_time} ms\n")
                async_file_hander.write(spectra_path, f"Number of Averages: {self.num_avg}\n")
                async_file_hander.write(spectra_path, "\n")
                async_file_hander.write(spectra_path, "wavelength (nm),counts\n")
                for wavelength, counts in zip(self.spectrum[0], self.spectrum[1]):
                    async_file_hander.write(spectra_path, f"{wavelength},{counts}\n") 
                    
# ### wavelength and power desity export to the print file is this section... Its a csv
                # Save irradiance to file
                irradiance_path = str(self.current_job / f"{path_prefix}_irradiance_{light_engine}_{wavelength}.csv")
                async_file_hander.write(irradiance_path, f"Default wavelength {self.default_wavelength} dB\n")
                async_file_hander.write(irradiance_path, f"Irradiance {self.default_wavelength} dB\n")
                async_file_hander.write(irradiance_path, "wavelength (nm),counts\n")
                for wavelength, counts in zip(self.irradiance[0], self.irradiance[1]):
                    async_file_hander.write(irradiance_path, f"{wavelength},{counts}\n")
                
    def measure_spectra(self):
            log.info(f"Calculating spectrometer integration time")
            self.integration_time = self.spectrometer.set_integration_time(None)
            log.info(f"Measuring spectra")
            self.spectrum = self.spectrometer.get_spectrum(self.num_avg)
            
    def measure_irradiance(self):
            log.info(f"Measuring irradiance")   
            self.irradiance = self.photodiode.get_power_density(self.default_wavelength)