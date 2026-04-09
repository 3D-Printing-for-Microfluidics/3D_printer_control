import os
import time
import logging
import json
from datetime import datetime
from pathlib import Path

import printer_server.views.home as home
from printer_server.settings import Config
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.printer_control.print_control import PrintControl, run_in_thread
from printer_server.views.manual_controls import update_le_led_state, update_screen_preview
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles
from printer_server.print_file_validator import check_version

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class LightMeasurementControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.light_engines = driver_handles.light_engines
        if "spectrometer" in config_dict:
            self.spectrometer = driver_handles.spectrometer
        if "photodiode" in config_dict:
            self.photodiode = driver_handles.photodiode
            

    def connect_hardware(self):
        # Connect spectrometer and photodiode
        if "spectrometer" in config_dict:
            spectrometer_thread = Thread(log, name="spectrometer_connect_thread", target=self.spectrometer.connect)
            spectrometer_thread.start()
        if "photodiode" in config_dict:
            photodiode_thread = Thread(log, name="photodiode_connect_thread", target=self.photodiode.connect)
            photodiode_thread.start()
        super().connect_hardware()
        if "spectrometer" in config_dict:
            spectrometer_thread.join()
        if "photodiode" in config_dict:
            photodiode_thread.join()
        if "spectrometer" in config_dict:
            if not self.spectrometer.connected or spectrometer_thread.exception is not None:
                log.error("Spectrometer failed to connect!")
                self.failed_hardware["Spectrometer"] = self.spectrometer
        if "photodiode" in config_dict:
            if not self.photodiode.connected or photodiode_thread.exception is not None:
                log.error("Photodiode failed to connect!")
                self.failed_hardware["Photodiode"] = self.photodiode

    def initialize_hardware(self):
        if "photodiode" in config_dict:
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
                if check_version(self.print_settings) != "v999":
                    self.measure_light("preprint", adjust_normalization_factor=True)
            except Exception as ex:
                log.warning("Error occured during light measurement (%s)", ex, exc_info=True)

    def post_print_tasks(self):
        if not (self.printing_stopped.is_set() or self.printing_paused.is_set()):
            try:
                if check_version(self.print_settings) != "v999":
                    self.measure_light("postprint", adjust_normalization_factor=False)
            except Exception as ex:
                log.warning("Error occured during light measurement (%s)", ex, exc_info=True)
        super().post_print_tasks()

    def _get_last_calibration_positions_from_logs(self):
        log_file = Path(Config.PROJECT_ROOT) / "logs" / "calibration_position_log.txt"
        last_line = None
        try:
            with open(log_file) as file_handle:
                for line in file_handle:
                    last_line = line.rstrip()
            if not last_line:
                return {}
            last_line = last_line[20:]
            last_line = last_line.replace("'", '"')
            return json.loads(last_line)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

    def _get_irradiance_target(self, light_engine, wavelength):
        positions = self._get_last_calibration_positions_from_logs()
        key = f"irradiance_target_{light_engine}_{wavelength}"
        return positions.get(key)

    def _update_normalization_factor(self, light_engine_driver, light_engine, led_num, new_value, is_grayscale=False):
        key = "grayscale_normalization_factor" if is_grayscale else "normalization_factor"
        if key not in light_engine_driver.config_dict:
            if "normalization_factor" in light_engine_driver.config_dict:
                light_engine_driver.config_dict[key] = light_engine_driver.config_dict["normalization_factor"].copy()
            else:
                light_engine_driver.config_dict[key] = [1.0] * len(config_dict.get(light_engine, {}).get("leds_nm", []))
        if key not in config_dict.get(light_engine, {}):
            config_dict[light_engine][key] = light_engine_driver.config_dict[key].copy()

        if led_num >= len(light_engine_driver.config_dict[key]):
            missing = (led_num + 1) - len(light_engine_driver.config_dict[key])
            light_engine_driver.config_dict[key].extend([1.0] * missing)
        if led_num >= len(config_dict[light_engine][key]):
            missing = (led_num + 1) - len(config_dict[light_engine][key])
            config_dict[light_engine][key].extend([1.0] * missing)

        light_engine_driver.config_dict[key][led_num] = new_value
        config_dict[light_engine][key][led_num] = new_value

    def measure_light(self, path_prefix, adjust_normalization_factor=False):
        for light_engine in config_dict["light_engines"]:
            
            # Move x/y/focus to spectrometer location
            self.move_xyf_stages_in_coordinate_system(
                coord_system_name=f"fiber_{light_engine}",
                x=0,
                y=0,
                f=0,
                light_engine=light_engine
            )

            # Setup light engines
            for i, wavelength in enumerate(config_dict[light_engine]["leds_nm"]):
                light_engine_driver = self.light_engines[light_engine]

                integration_time = None
                spectrum = None
                irr = None
                irr_adj = None
                irr_gray = None
                irr_gray_adj = None
                target = self._get_irradiance_target(light_engine, wavelength)
                if "spectrometer" in config_dict:
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
                if "spectrometer" in config_dict:
                    try:
                        integration_time, spectrum = self.measure_spectra(num_avg)
                    except:
                        log.warning("Unable to measure spectra")
                if "photodiode" in config_dict:
                    try:
                        irr = self.measure_irradiance(wavelength)
                    except:
                        log.warning("Unable to measure irradiance")

                if adjust_normalization_factor and "photodiode" in config_dict and irr is not None:
                    if target is not None and target > 0 and irr > 0:
                        count = 0
                        irr_adj = irr
                        while abs(target - irr_adj) / target > 0.015 and count < 3:
                            current_nf = light_engine_driver.config_dict.get("normalization_factor", [1.0])[i]
                            updated_nf = round(current_nf * (target / irr_adj), 2)
                            self._update_normalization_factor(
                                light_engine_driver, light_engine, i, updated_nf, is_grayscale=False
                            )
                            try:
                                light_engine_driver.stop_sequencer()
                                light_engine_driver.setup_exposure(10000, led_power=100, repeat=0, is_grayscale_corrected=False, led_num=i)
                                light_engine_driver.perform_exposure()
                                time.sleep(0.1)
                                _irr_adj = self.measure_irradiance(wavelength)
                            except:
                                log.warning("Unable to measure adjusted irradiance")

                            if abs(target - _irr_adj) / target < abs(target - irr_adj) / target:
                                log.info(
                                    "Updated normalization factor for %s %s nm to %s (target=%s, measured=%s, corrected=%s)",
                                    light_engine,
                                    wavelength,
                                    updated_nf,
                                    target,
                                    irr_adj,
                                    _irr_adj,
                                )
                                irr_adj = _irr_adj
                            else:
                                self._update_normalization_factor(
                                    light_engine_driver, light_engine, i, current_nf, is_grayscale=False
                                )
                                break
                            count += 1

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

                if "photodiode" in config_dict:
                    try:
                        irr_gray = self.measure_irradiance(wavelength)
                    except:
                        log.warning("Unable to measure irradiance")  

                if adjust_normalization_factor and "photodiode" in config_dict and irr_gray is not None:
                    if target is not None and target > 0 and irr_gray > 0:
                        count = 0
                        irr_gray_adj = irr_gray
                        while abs(target - irr_gray_adj) / target > 0.015 and count < 3:
                            current_gray_nf = light_engine_driver.config_dict.get(
                                "grayscale_normalization_factor",
                                light_engine_driver.config_dict.get("normalization_factor", [1.0]),
                            )[i]
                            updated_gray_nf = round(current_gray_nf * (target / irr_gray_adj), 2)
                            self._update_normalization_factor(
                                light_engine_driver, light_engine, i, updated_gray_nf, is_grayscale=True
                            )
                            try:
                                light_engine_driver.stop_sequencer()
                                light_engine_driver.setup_exposure(10000, led_power=100, repeat=0, is_grayscale_corrected=True, led_num=i)
                                light_engine_driver.perform_exposure()
                                time.sleep(0.1)
                                _irr_gray_adj = self.measure_irradiance(wavelength)
                            except:
                                log.warning("Unable to measure adjusted irradiance")

                            if abs(target - _irr_gray_adj) / target < abs(target - irr_gray_adj) / target:
                                log.info(
                                    "Updated grayscale normalization factor for %s %s nm to %s (target=%s, measured=%s, corrected=%s)",
                                    light_engine,
                                    wavelength,
                                    updated_gray_nf,
                                    target,
                                    irr_gray_adj,
                                    _irr_gray_adj
                                )
                                irr_gray_adj = _irr_gray_adj
                            else:
                                self._update_normalization_factor(
                                    light_engine_driver, light_engine, i, current_gray_nf, is_grayscale=True
                                )
                                break
                            count += 1

                # Turn off light engine
                light_engine_driver.stop_sequencer()
                update_le_led_state(light_engine, False)

                # Save spectrum to file
                light_measurement_path = str(self.current_job / "logs" / f"{path_prefix}_Light_Measurement_{light_engine}_{wavelength}_nm.csv")
                async_file_hander.write(light_measurement_path, f"Wavelength: {wavelength} (nm)\n")
                async_file_hander.write(light_measurement_path, f"Irradiance target: {target} mW/cm^2\n")
                async_file_hander.write(light_measurement_path, f"Irradiance: {irr_adj} mW/cm^2\n")     
                async_file_hander.write(light_measurement_path, f"Irradiance (grayscale corrected): {irr_gray_adj} mW/cm^2\n")               
                if "spectrometer" in config_dict:
                    async_file_hander.write(light_measurement_path, f"Integration time: {integration_time} ms\n")
                    async_file_hander.write(light_measurement_path, f"Number of Averages: {num_avg}\n")
                async_file_hander.write(light_measurement_path, "\n")
                if "spectrometer" in config_dict:
                    if spectrum is not None:
                        async_file_hander.write(light_measurement_path, "wavelength (nm),counts\n")
                        for _wavelength, _counts in zip(spectrum[0], spectrum[1]):
                            async_file_hander.write(light_measurement_path, f"{_wavelength},{_counts}\n") 
                    
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