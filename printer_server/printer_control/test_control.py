import time
import math
import logging
import numpy as np
import pandas as pd
from PIL import Image
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from scipy.interpolate import griddata

import printer_server.views.home as home
from printer_server.settings import Config
from printer_server.async_file_handler import async_file_hander
from printer_server.printer_control.print_control import PrintControl
from printer_server.hardware_configuration.hardware_configuration import config_dict

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# sample_rate_hz = 1/300
# time_to_process = 0.0033

class TestControl(PrintControl):
    def test_worker(self):
        self.printing_stopped.clear()

        funcs = self.print_settings["Functions"]
        for f_dict in funcs:
            f_name = f_dict["name"]
            f = getattr(self, f_name, None)
            if f is None:
                log.error(f"Function '{f_name}' not found in {self.__class__.__name__}")
            else:
                if "kwargs" in f_dict.keys():
                    f(**f_dict["kwargs"])
                else:
                    f()
        self.finish_print()

    def setup_tests(self):
        self.pre_print_tasks()
        self.pre_print_joins()

        # Setup
        self.slices_folder = Path(self.print_settings["Header"]["Image directory"])
        self.photodiode.set_wavelength(365)
        self.photodiode.set_num_averages(2)
        self.photodiode.zero()

        self.light_engine = "visitech"
        self.led_num = 0
        self.screen.setCorrectionEnable(False, False, light_engine=self.light_engine)

    def cleanup_tests(self):
        self.post_print_tasks()
        self.post_print_joins()

        # Reset photodiode averages
        self.photodiode.set_num_averages(self.photodiode.defaultAverages)

    def ultrafast_photodiode_tests(self):
        from printer_server.drivers.generic_drivers.usb_serial import USBSerial
        from printer_server.threading_wrapper import Thread

        self.xy_stage.threadedXYMove(log, -25.00, 85.56, join=True)
        self.focus_stage.absMoveFocus(mm=6.00)

        self.light_engines[self.light_engine].setup_exposure(1000, led_power=200, repeat=0, is_grayscale_corrected=False, led_num=self.led_num)
        self.light_engines[self.light_engine].perform_exposure()

        u = USBSerial("Fast photodiode", vid=5824, pid=1155, sn="16040530", multiline=True)
        u.connect()

        images = [
            "image_with_grayscale_0", 
            "image_with_grayscale_1", 
            "image_with_grayscale_2", 
            "image_with_grayscale_4", 
            "image_with_grayscale_8", 
            "image_with_grayscale_16", 
            "image_with_grayscale_32", 
            "image_with_grayscale_64", 
            "image_with_grayscale_128", 
            "image_with_grayscale_254", 
            "image_with_grayscale_255"
        ]

        # repeat tests
        for i, image_name in enumerate(images):
            self.screen.draw(self.current_job / self.slices_folder / f"{image_name}.png", light_engine=self.light_engine, led_num=self.led_num)
            time.sleep(0.1)
            log.info("Starting test")
            result = u.send("c")
            log.info("Writing data")
            log_name = str(self.current_job / "logs" / f"{image_name}_repeat.csv")
            async_file_hander.write(log_name, result)
            log.info("Test done")

            msg = {
                "percent": int(100 * (i+1) / (len(images)*2)),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            }
            home.update_printer_state("print progress", msg)

        # 500ms tests
        for i, image_name in enumerate(images):
            self.screen.draw(self.current_job / self.slices_folder / f"{image_name}.png", light_engine=self.light_engine, led_num=self.led_num)
            self.light_engines[self.light_engine].stop_sequencer()
            self.light_engines[self.light_engine].setup_exposure(300, led_power=200, repeat=1, is_grayscale_corrected=False, led_num=self.led_num)
            time.sleep(0.1)
            log.info("Starting test")
            thread = Thread(
                log, 
                name=f"visitech_setup_thread",
                target=self.light_engines[self.light_engine].perform_exposure,
            )
            thread.start()
            result = u.send("c")
            thread.join()
            log.info("Writing data")
            log_name = str(self.current_job / "logs" / f"{image_name}_500ms.csv")
            async_file_hander.write(log_name, result)
            log.info("Test done")

            msg = {
                "percent": int(100 * (i+len(images)+1) / (len(images)*2)),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            }
            home.update_printer_state("print progress", msg)
        u.disconnect()

        self.light_engines[self.light_engine].stop_sequencer()

    def measure_keyence_line(self, step_size=0.15, scan_length_mm=25, number_of_scans=3, scan_spacing_mm=2.0, y_offset_mm=0.0):
        if self.printing_stopped.is_set():
            return
        ################ Step ################
        # Setup file
        self.test_log = str(self.current_job / "logs" / f"test_data.csv")
        async_file_hander.write(
                self.test_log, "time,measurement,x,y,\n"
            )

        x_size = scan_length_mm
        x_keyence_offset = self.coord_systems["keyence_visitech"]["X"]
        y_keyence_offset = self.coord_systems["keyence_visitech"]["Y"]
        x_pos_sweep = x_keyence_offset - x_size/2 - step_size
        x_range = round((x_size+2*step_size)/step_size) + 1
        x_set = []
        y_set = []
        for x in range(x_range):
            x_set.append(x_pos_sweep+x*step_size)
        for y in range(number_of_scans):
            y_set.append(y_keyence_offset - (number_of_scans-1)*scan_spacing_mm/2 + y*scan_spacing_mm + y_offset_mm)

        # Move to x start
        self.xy_stage.threadedXYMove(log, x_set[0], y_set[0], join=True)
                    
        for y_index, y in enumerate(y_set):
            for x_index, x in enumerate(x_set):
                self.xy_stage.threadedXYMove(
                    log, 
                    x,
                    y,
                    speed_x=50,
                    speed_y=50,
                    acceleration_x=100,
                    acceleration_y=100, 
                    join=True
                )

                # Wait
                time.sleep(0.1)

                # Get Position
                x_position = self.xy_stage.getXYPosition(axis="X")
                y_position = self.xy_stage.getXYPosition(axis="Y")
                x_position -= x_keyence_offset
                y_position -= y_keyence_offset

                # Log measurements
                # Start time
                t = datetime.now() - self.print_start_time 
                async_file_hander.write(self.test_log, f"{t},")

                # Get Photodiode power
                async_file_hander.write(self.test_log, f"{self.keyence.read_sensor('visitech')},")
                async_file_hander.write(self.test_log, f"{x_position:.3f},{y_position:.3f},")
                async_file_hander.write(self.test_log, f"\n")

                # Wait
                time.sleep(0.1)

                if self.printing_stopped.is_set():
                    return

                msg = {
                    "percent": int(100 * (len(x_set)*y_index+x_index+1) / (len(x_set)*len(y_set))),
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                }
                home.update_printer_state("print progress", msg)


    def measure_spectra_and_power(self, filename="spectra.csv"):
        if self.printing_stopped.is_set():
            return
        # Move to center
        x_pos = self.coord_systems["fiber_visitech"]["X"]
        y_pos =  self.coord_systems["fiber_visitech"]["Y"]
        self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=True)

        # Draw white
        self.screen.draw(self.current_job / self.slices_folder / "white.png", light_engine=self.light_engine, led_num=self.led_num)

        self.light_engines[self.light_engine].setup_exposure(1000, led_power=100, repeat=0, is_grayscale_corrected=True, led_num=self.led_num)
        self.light_engines[self.light_engine].perform_exposure()

        # Read spectra and exp
        integration_time = self.spectrometer.set_integration_time(None)
        spectrum = self.spectrometer.get_spectrum(100)

        irradiances = []
        for _ in range(100):
            irradiances.append(self.photodiode.get_power_density())
            time.sleep(0.01)
        irradiance =  sum(irradiances)/len(irradiances)

        spectra_path = str(self.current_job / "logs" / filename)
        async_file_hander.write(spectra_path, f"Wavelength: 365 (nm)\n")
        async_file_hander.write(spectra_path, f"Irradiance: {irradiance} mW/cm^2\n")               
        async_file_hander.write(spectra_path, f"Integration time: {integration_time} ms\n")
        async_file_hander.write(spectra_path, f"Number of Averages: 100\n")
        async_file_hander.write(spectra_path, "\n")
        if spectrum is not None:
            async_file_hander.write(spectra_path, "wavelength (nm),counts\n")
            for _wavelength, _counts in zip(spectrum[0], spectrum[1]):
                async_file_hander.write(spectra_path, f"{_wavelength},{_counts}\n") 

        self.light_engines[self.light_engine].stop_sequencer()
    
    def find_photodiode_center_and_focus(self, find_corners=False):
        self.test_log = str(self.current_job / "logs" / "xyz_test_data.csv")

        if find_corners:
            orders = ["X", "Y", "X", "Y"]
            step_sizes = [0.01, 0.01, 0.0025, 0.0025]
            step_counts = [20, 20, 20, 20]
            images = ["v_4px_cent.png", "v_4px_cent.png", "v_4px_cent.png", "v_4px_cent.png"]
            use_find_peaks = [False, False, False, False]
            use_fits = [False, False, True, True]
        else:
            orders = ["X", "Y", "Focus", "X", "Y", "X", "Y", "Focus"]
            step_sizes = [0.1, 0.1, 0.1, 0.01, 0.01, 0.0025, 0.0025, 0.01]
            step_counts = [20, 20, 100, 20, 20, 20, 20, 50]
            images = ["v_4px_horz.png", "v_4px_vert.png", "v_4px_cent.png", "v_4px_cent.png", "v_4px_cent.png", "v_4px_cent.png", "v_4px_cent.png", "v_4px_cent.png"]
            use_find_peaks = [False, False, True, False, False, False, False, False]
            use_fits = [False, False, False, False, False, True, True, True]

        if not find_corners:
            # Move to rough position
            x_pos = self.coord_systems["fiber_visitech"]["X"]
            y_pos = self.coord_systems["fiber_visitech"]["Y"]
            z_pos = self.coord_systems["fiber_visitech"]["Focus"]
            self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=True)
            self.focus_stage.absMoveFocus(mm=z_pos)

        self.light_engines[self.light_engine].setup_exposure(1000, led_power=100, repeat=0, is_grayscale_corrected=False, led_num=self.led_num)
        self.light_engines[self.light_engine].perform_exposure()

        for stage, step_size, step_count, image, _use_find_peaks, use_fit in zip(orders, step_sizes, step_counts, images, use_find_peaks, use_fits):
            if self.printing_stopped.is_set():
                return
            
            # Draw image
            self.screen.draw(self.current_job / self.slices_folder / image, light_engine=self.light_engine, led_num=self.led_num)
            irr_list = []
            pos_list = []

            # Move to start
            if stage == "X" or stage == "Y":
                
                pos = self.xy_stage.getXYPosition(axis=stage) - step_count*step_size/2
                self.xy_stage.absMoveXY(mm=pos, axis=stage)
            else:
                pos = self.focus_stage.getFocusPosition() - step_count*step_size/2
                self.focus_stage.absMoveFocus(mm=pos)

            # Measure power
            time.sleep(0.05)
            pos_list.append(pos)
            irr_list.append(self.photodiode.get_power_density())
            for i in range(step_count):
                # Step stage
                pos += step_size
                if stage in ["X", "Y"]:
                    self.xy_stage.absMoveXY(mm=pos, axis=stage)
                else:
                    self.focus_stage.absMoveFocus(mm=pos)

                # Measure power
                time.sleep(0.05)
                pos_list.append(pos)
                irr_list.append(self.photodiode.get_power_density())

                if self.printing_stopped.is_set():
                    return

            pos -= step_count*step_size

            # find peak
            if use_fit:
                coefficients = np.polyfit(pos_list, irr_list, 4)
                polynomial = np.poly1d(coefficients)
                fit_list = polynomial(pos_list)
                fit_list = fit_list.tolist()
                max_val = max(fit_list)
                max_index = fit_list.index(max_val)
                peak_pos = pos_list[max_index]

            elif _use_find_peaks:
                prominence_threshold = 0.25
                peak_indices, properties = find_peaks(irr_list, prominence=prominence_threshold)
                prominences = properties['prominences']
                filtered_peak_indices = [index for i, index in enumerate(peak_indices) if prominences[i] > prominence_threshold]
                if len(filtered_peak_indices) < 2:
                    max_val = max(irr_list)
                    max_index = irr_list.index(max_val)
                    peak_pos = pos_list[max_index]
                else:
                    top_two_peaks = sorted(filtered_peak_indices, key=lambda x: irr_list[x], reverse=True)[:2]
                    peak1, peak2 = sorted(top_two_peaks)
                    valley_index = np.argmin(irr_list[peak1:peak2 + 1]) + peak1
                    valley_position = pos_list[valley_index]
                    valley_value = irr_list[valley_index]
                    peak_pos = pos_list[valley_index]

            else:
                max_val = max(irr_list)
                max_index = irr_list.index(max_val)
                peak_pos = pos_list[max_index]

            # Move to finish
            if stage in ["X", "Y"]:
                self.xy_stage.absMoveXY(mm=peak_pos, axis=stage)
            else:
                self.focus_stage.absMoveFocus(mm=peak_pos)
            if not find_corners:
                self.coord_systems["fiber_visitech"][stage] = peak_pos

            # Log peak
            log.info(pos_list)
            log.info(irr_list)
            if use_fit:
                log.info(fit_list)

            async_file_hander.write(self.test_log, f"{pos_list}\n")
            async_file_hander.write(self.test_log, f"{irr_list}\n")
            if use_fit:
                async_file_hander.write(self.test_log, f"{fit_list}\n")
            async_file_hander.write(self.test_log, f"X:{self.xy_stage.getXYPosition(axis='X'):.3f} Y:{self.xy_stage.getXYPosition(axis='Y'):.3f} Z:{self.focus_stage.getFocusPosition()}\n")
            async_file_hander.write(self.test_log, f"\n")

        self.light_engines[self.light_engine].stop_sequencer()
        
    def measure_grayscale_at_center(self, sample_rate_hz=80):
        self.test_log = str(self.current_job / "logs" / "gray_test_data.csv")
        async_file_hander.write(
            self.test_log, "time,grayvalue,irradiance,\n"
        )

        self.light_engines[self.light_engine].setup_exposure(1000, led_power=100, repeat=0, is_grayscale_corrected=False, led_num=self.led_num)
        self.light_engines[self.light_engine].perform_exposure()
        
        for i in range(256):
            if self.printing_stopped.is_set():
                return
            self.screen.draw(self.current_job / self.slices_folder / f"image_with_grayscale_{i}.png", light_engine=self.light_engine, led_num=self.led_num)

            # Wait
            time.sleep(0.1)

            log.info(f"{i}: {self.photodiode.get_power_density()}")

            time.sleep(0.01)

            # Log measurements
            for _ in range(150):
                # Start time
                t = datetime.now() - self.print_start_time 
                async_file_hander.write(self.test_log, f"{t},")

                # Get Photodiode power
                irradiance = self.photodiode.get_power_density()
                async_file_hander.write(self.test_log, f"{i},")
                async_file_hander.write(self.test_log, f"{irradiance},")
                async_file_hander.write(self.test_log, f"\n")

                # Wait
                time_to_process = 0.0033
                time.sleep(1/sample_rate_hz - time_to_process)

            msg = {
                "percent": int(100 * (i+1) / (256)),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            }
            home.update_printer_state("print progress", msg)

        self.light_engines[self.light_engine].stop_sequencer()

    def measure_irradiance_line(self, step_size=0.05, sample_rate_hz=80, sweep_px=[1600,2560], image_name="white.png"):
        if self.printing_stopped.is_set():
            return
        ################ Step ################
        # Setup file
        if image_name == "white.png":
           self.test_log = str(self.current_job / "logs" / f"test_data.csv")
        else: 
            self.test_log = str(self.current_job / "logs" / f"test_data_{image_name}.csv")
        async_file_hander.write(
                self.test_log, "time,irradiance,x,y,\n"
            )

        # Draw correction image
        if image_name is not None:
            self.screen.draw(self.current_job / self.slices_folder / image_name, light_engine=self.light_engine, led_num=self.led_num)

            self.light_engines[self.light_engine].setup_exposure(1000, led_power=100, repeat=0, is_grayscale_corrected=True, led_num=self.led_num)
            self.light_engines[self.light_engine].perform_exposure()

        x_size = sweep_px[0]*0.0076
        y_size = sweep_px[1]*0.0076

        x_pos_fixed = self.coord_systems["fiber_visitech"]["X"]
        y_pos_fixed = self.coord_systems["fiber_visitech"]["Y"]
        x_pos_sweep = self.coord_systems["fiber_visitech"]["X"] - x_size/2 - step_size
        y_pos_sweep = self.coord_systems["fiber_visitech"]["Y"] - y_size/2 - step_size
        x_range = round((x_size+2*step_size)/step_size) + 1
        y_range = round((y_size+2*step_size)/step_size) + 1
        x_set = []
        y_set = []
        for x in range(x_range):
            x_set.append(x_pos_sweep+x*step_size)
        for y in range(y_range):
            y_set.append(y_pos_sweep+y*step_size)
        
        # Move to y start
        self.xy_stage.threadedXYMove(log, x_pos_fixed, y_pos_sweep, join=True)

        for y_index, y in enumerate(y_set):
            self.xy_stage.threadedXYMove(
                log, 
                x_pos_fixed,
                y,
                speed_x=50,
                speed_y=50,
                acceleration_x=100,
                acceleration_y=100, 
                join=True
            )

            # Wait
            time.sleep(0.1)

            # Get Position
            x_position = self.xy_stage.getXYPosition(axis="X")
            y_position = self.xy_stage.getXYPosition(axis="Y")
            x_position -= self.coord_systems["fiber_visitech"]["X"]
            y_position -= self.coord_systems["fiber_visitech"]["Y"]

            # Log measurements
            for _ in range(40):
                # Start time
                t = datetime.now() - self.print_start_time 
                async_file_hander.write(self.test_log, f"{t},")

                # Get Photodiode power
                irradiance = self.photodiode.get_power_density()
                async_file_hander.write(self.test_log, f"{irradiance},")
                async_file_hander.write(self.test_log, f"{x_position:.3f},{y_position:.3f},")
                async_file_hander.write(self.test_log, f"\n")

                # Wait
                time_to_process = 0.0033
                time.sleep(1/sample_rate_hz - time_to_process)

                if self.printing_stopped.is_set():
                    return

            msg = {
                "percent": int(100 * (y_index+1) / (len(y_set)+len(x_set))),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            }
            home.update_printer_state("print progress", msg)

        # Move to x start
        self.xy_stage.threadedXYMove(log, x_pos_sweep, y_pos_fixed, join=True)
                    
        for x_index, x in enumerate(x_set):
            self.xy_stage.threadedXYMove(
                log, 
                x,
                y_pos_fixed,
                speed_x=50,
                speed_y=50,
                acceleration_x=100,
                acceleration_y=100, 
                join=True
            )

            # Wait
            time.sleep(0.1)

            # Get Position
            x_position = self.xy_stage.getXYPosition(axis="X")
            y_position = self.xy_stage.getXYPosition(axis="Y")
            x_position -= self.coord_systems["fiber_visitech"]["X"]
            y_position -= self.coord_systems["fiber_visitech"]["Y"]

            # Log measurements
            for _ in range(40):
                # Start time
                t = datetime.now() - self.print_start_time 
                async_file_hander.write(self.test_log, f"{t},")

                # Get Photodiode power
                irradiance = self.photodiode.get_power_density()
                async_file_hander.write(self.test_log, f"{irradiance},")
                async_file_hander.write(self.test_log, f"{x_position:.3f},{y_position:.3f},")
                async_file_hander.write(self.test_log, f"\n")

                # Wait
                time_to_process = 0.0033
                time.sleep(1/sample_rate_hz - time_to_process)

                if self.printing_stopped.is_set():
                    return

            msg = {
                "percent": int(100 * (len(y_set)+x_index+1) / (len(x_set)+len(y_set))),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            }
            home.update_printer_state("print progress", msg)

        if image_name is not None:
            self.light_engines[self.light_engine].stop_sequencer()


    # Measures the 4 corners to find out the exact pixel size in x and y
    def find_px_size(self):
        x_px = 1600
        y_px = 2560
        
        x_px_size = 0.00756
        y_px_size = 0.00756

        focus_spot_px = 4

        # Find 4 corners
        x_pos = self.coord_systems["fiber_visitech"]["X"] - (x_px-focus_spot_px)*x_px_size/2
        y_pos = self.coord_systems["fiber_visitech"]["Y"] - (y_px-focus_spot_px)*y_px_size/2
        self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=True)
        self.find_photodiode_center_and_focus(find_corners=True)
        x1 = self.xy_stage.getXYPosition(axis="X")
        y1 = self.xy_stage.getXYPosition(axis="Y")
        
        x_pos = self.coord_systems["fiber_visitech"]["X"] - (x_px-focus_spot_px)*x_px_size/2
        y_pos = self.coord_systems["fiber_visitech"]["Y"] + (y_px-focus_spot_px)*y_px_size/2
        self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=True)
        self.find_photodiode_center_and_focus(find_corners=True)
        x2 = self.xy_stage.getXYPosition(axis="X")
        y2 = self.xy_stage.getXYPosition(axis="Y")
        
        x_pos = self.coord_systems["fiber_visitech"]["X"] + (x_px-focus_spot_px)*x_px_size/2
        y_pos = self.coord_systems["fiber_visitech"]["Y"] + (y_px-focus_spot_px)*y_px_size/2
        self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=True)
        self.find_photodiode_center_and_focus(find_corners=True)
        x3 = self.xy_stage.getXYPosition(axis="X")
        y3 = self.xy_stage.getXYPosition(axis="Y")

        x_pos = self.coord_systems["fiber_visitech"]["X"] + (x_px-focus_spot_px)*x_px_size/2
        y_pos = self.coord_systems["fiber_visitech"]["Y"] - (y_px-focus_spot_px)*y_px_size/2
        self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=True)
        self.find_photodiode_center_and_focus(find_corners=True)
        x4 = self.xy_stage.getXYPosition(axis="X")
        y4 = self.xy_stage.getXYPosition(axis="Y")

        # Calculate x/y pixel size
        log.info(f"y1: {math.sqrt((x1-x2)**2+(y1-y2)**2)}")
        log.info(f"x1: {math.sqrt((x2-x3)**2+(y2-y3)**2)}")
        log.info(f"y2: {math.sqrt((x3-x4)**2+(y3-y4)**2)}")
        log.info(f"x2: {math.sqrt((x4-x1)**2+(y4-y1)**2)}")

        log.info(f"x: {(math.sqrt((x2-x3)**2+(y2-y3)**2) + math.sqrt((x4-x1)**2+(y4-y1)**2))/2}")
        log.info(f"y: {(math.sqrt((x1-x2)**2+(y1-y2)**2) + math.sqrt((x3-x4)**2+(y3-y4)**2))/2}")
        
        self.x_px_size = (math.sqrt((x2-x3)**2+(y2-y3)**2) + math.sqrt((x4-x1)**2+(y4-y1)**2))/2/(x_px-focus_spot_px)
        self.y_px_size = (math.sqrt((x1-x2)**2+(y1-y2)**2) + math.sqrt((x3-x4)**2+(y3-y4)**2))/2/(y_px-focus_spot_px)
        log.info(f"xpx: {self.x_px_size}, ypx: {self.y_px_size}")
       

    # Measures the irradiance in a grid of every 150 or 15 px 
    # Should run find_photodiode_center_and_focus and find_px_size first
    def measure_irradiance_grid2(self, fine=True, save_name = "test_data.csv"):
        if self.printing_stopped.is_set():
            return

        ################ Step ################
        # Setup file
        test_log = str(self.current_job / "logs" / save_name)
        async_file_hander.write(
                test_log, "time,irradiance,x,y,\n"
            )
        
        x_px = 1600
        y_px = 2560
        
        if fine:
            # note: 15 & 30 are both factors of both 1590 and 1550 (our spot is 10px, so - 5 from each side)
            # x_range = range(5, x_px, 15)
            # y_range = range(5, y_px, 15)
            x_range = range(5, x_px, 30)
            y_range = range(5, y_px, 30)
            # x_range = range(5, x_px, 53)
            # y_range = range(5, y_px, 51)
        else:
            # note: 159 and 150 are factors of 1590 and 1550 respectively
            x_range = range(5, x_px, 159)
            y_range = range(5, y_px, 150)
            # x_range = range(5, x_px, 530)
            # y_range = range(5, y_px, 510)

        self.light_engines[self.light_engine].setup_exposure(1000, led_power=100, repeat=0, is_grayscale_corrected=False, led_num=self.led_num)
        self.light_engines[self.light_engine].perform_exposure()

        for x_index, x in enumerate(x_range):
            for y_index, y in enumerate(y_range):
                # Move to location
                x_pos = self.coord_systems["fiber_visitech"]["X"] + (x - x_px/2)*self.x_px_size
                y_pos = self.coord_systems["fiber_visitech"]["Y"] + (y - y_px/2)*self.y_px_size
                self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=True)

                # for index, spot_value, bulk_value in zip([0, 1], [0, 255], [255, 255]):
                spot_value = 255
                bulk_value = 255
                # Create image (with 10px spot sizes)
                # notes:
                # the image and physical coords are swapped (x->y & y->x)
                # the image is mirrored in the short direction
                image_array = np.full((x_px, y_px), bulk_value, dtype=np.uint8)
                x_start = max(y - 5, 0) 
                x_end = min(y + 5, y_px)
                y_start = x_px - min(x + 5, x_px)
                y_end = x_px - max(x - 5, 0)
                image_array[y_start:y_end, x_start:x_end] = spot_value
                image = Image.fromarray(image_array, mode='L')
                image.save(self.current_job / self.slices_folder / f"temp.png")  # Saves the image

                # Draw correction image
                self.screen.draw(self.current_job / self.slices_folder / f"temp.png", light_engine=self.light_engine, led_num=self.led_num)

                # Get Position
                x_position = self.xy_stage.getXYPosition(axis="X")
                y_position = self.xy_stage.getXYPosition(axis="Y")
                x_position -= self.coord_systems["fiber_visitech"]["X"]
                y_position -= self.coord_systems["fiber_visitech"]["Y"]

                # Log measurements
                for _ in range(40):
                    # Start time
                    t = datetime.now() - self.print_start_time 
                    async_file_hander.write(test_log, f"{t},")

                    # Get Photodiode power
                    irradiance = self.photodiode.get_power_density()
                    async_file_hander.write(test_log, f"{irradiance},")
                    async_file_hander.write(test_log, f"{x_position:.3f},{y_position:.3f},")
                    async_file_hander.write(test_log, f"\n")

                    # Wait
                    time_to_process = 0.0033
                    # photodiode sample rate of 150 fps
                    time.sleep(1/300 - time_to_process)

                    if self.printing_stopped.is_set():
                        return

                msg = {
                    "percent": int(100 * (x_index*len(y_range)+y_index+1) / (len(x_range)*len(y_range))),
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                }
                home.update_printer_state("print progress", msg)

        self.light_engines[self.light_engine].stop_sequencer()


    def _createCorrectionImage(self, filename, save_directory_name, irradiance_map, light_correction=True, remove_outliers=True, grayscale_min=0.75):
        directory = self.current_job / "logs"
        x_pixels = 2560
        y_pixels = 1600
        width_space = np.linspace(0, x_pixels, x_pixels)
        height_space = np.linspace(0, y_pixels, y_pixels)
        X, Y = np.meshgrid(width_space, height_space)

        def load_data():
            log.info(f"\tLoading Data...")
            df = pd.read_csv(directory / filename)
            df = average_data(df, directory / save_directory_name / f"averaged_{filename}")
            x = df.iloc[:, 0]
            y = df.iloc[:, 1]
            z = df.iloc[:, 2]
            std = df.iloc[:, 3]
            irradiance_data = np.array([np.array(x), np.array(y), np.array(z), np.array(std)])
            return irradiance_data

        def average_data(df, avg_filename):
            if not remove_outliers:
                log.info(f"\tAveraging Data...")
                grouped_data = df.groupby(['x', 'y'])['irradiance'].agg(['mean', 'std']).reset_index()
                grouped_data.to_csv(avg_filename, index=False)
                return grouped_data
            else:
                log.info(f"\tCleaning Data...")
                # Step 1: Calculate initial group statistics
                initial_stats = df.groupby(['x', 'y'])['irradiance'].agg(['mean', 'std']).reset_index()
                median_std = initial_stats['std'].median()
                
                # Step 2: Identify outlier groups (std > 2.7x median_std)
                outlier_groups = initial_stats[initial_stats['std'] > 2.7 * median_std][['x', 'y']]
                
                # Initialize tracking for stats
                outlier_removal_stats = []

                # Step 3: Remove outlier points (±5 standard deviations) within the identified groups
                def remove_outliers_f2(group, x, y):
                    # group = group.reset_index()  # Ensure x and y are accessible
                    # group_key = (group['x'].iloc[0], group['y'].iloc[0])
                    group_key = (x, y)
                    if tuple(group_key) in outlier_groups.itertuples(index=False, name=None):
                        group_median = group['irradiance'].median()
                        group_std = group['irradiance'].std()
                        lower_bound = group_median - 0.5 * group_std
                        upper_bound = group_median + 0.5 * group_std
                        initial_count = len(group)
                        group = group[(group['irradiance'] >= lower_bound) & (group['irradiance'] <= upper_bound)]
                        removed_count = initial_count - len(group)
                        outlier_removal_stats.append((group_key, removed_count))
                    return group
                
                def remove_outliers_f(group):
                    x, y = group.name  # Extract grouping keys
                    filtered_data = remove_outliers_f2(group.copy(), x, y)
                    filtered_data.loc[:, 'x'] = x
                    filtered_data.loc[:, 'y'] = y
                    return filtered_data

                # Apply the outlier removal to all groups
                filtered_df = df.groupby(['x', 'y'], group_keys=False).apply(remove_outliers_f, include_groups=False)

                # Print stats on outliers
                total_groups_affected = len(outlier_removal_stats)
                total_outliers_removed = sum(count for _, count in outlier_removal_stats)
                log.info(f"\t\tTotal groups affected: {total_groups_affected}")
                for group_key, count in outlier_removal_stats:
                    log.info(f"\t\t\tGroup {float(group_key[0])}, {float(group_key[1])}: Removed {count} outliers")
                log.info(f"\t\tTotal outliers removed: {total_outliers_removed}")

                # Step 4: Calculate mean and std for the cleaned data
                log.info(f"\tAveraging Data...")
                grouped_data = filtered_df.groupby(['x', 'y'])['irradiance'].agg(['mean', 'std']).reset_index()

                # Save the results to a CSV file
                grouped_data.to_csv(avg_filename, index=False)
                
                return grouped_data

        def convert_to_pixel_space(irradiance_data):
            log.info(f"\tConverting to PX...")
            # compute actual image size
            # x_offset = 0.2314/2
            # y_offset = 0.2462/2
            x_offset = 0/2
            y_offset = 0/2

            physical_height = self.x_px_size*1600
            physical_width = self.y_px_size*2560

            # Swap axis
            pixel_data = np.array([irradiance_data[1, :], irradiance_data[0, :], irradiance_data[2, :], irradiance_data[3, :]])
            tmp = physical_height
            physical_height = physical_width
            physical_width = tmp
            _x_pixel_pitch = self.y_px_size
            _y_pixel_pitch = self.x_px_size
            tmp = x_offset
            x_offset = y_offset
            y_offset = tmp

            pixel_data[0, :] = (pixel_data[0, :] + physical_height/2 - x_offset) / _x_pixel_pitch
            pixel_data[1, :] = (pixel_data[1, :] + physical_width/2 - y_offset) / _y_pixel_pitch

            # Mirror x axis
            pixel_data[1, :] = (-pixel_data[1, :] + y_pixels)

            return pixel_data
        
        def map_data(pixel_data):
            log.info(f"\tMapping Data...")
            fit_data = griddata((pixel_data[0, :], pixel_data[1, :]), pixel_data[2, :], (X, Y), method='linear', fill_value=np.nan)
            stddev_data = griddata((pixel_data[0, :], pixel_data[1, :]), pixel_data[3, :], (X, Y), method='linear', fill_value=np.nan)

            fit_data_edges = griddata((pixel_data[0, :], pixel_data[1, :]), pixel_data[2, :], (X, Y), method='nearest')
            stddev_data_edges = griddata((pixel_data[0, :], pixel_data[1, :]), pixel_data[3, :], (X, Y), method='nearest')

            fit_data[np.isnan(fit_data)] = fit_data_edges[np.isnan(fit_data)]
            stddev_data[np.isnan(stddev_data)] = stddev_data_edges[np.isnan(stddev_data)]
            return fit_data, stddev_data
        
        def normalize_data(irradiance):
            log.info(f"\tNormalizing data...")
            return irradiance / np.max(irradiance)
        
        def create_correction_data(fit_data):
            log.info(f"\tCalculating correction...")
            fit_data_clipped = np.clip(fit_data, grayscale_min, 1.0)
            correction_data = (1/fit_data_clipped)/np.max(1/fit_data_clipped)
            return correction_data
        
        def save_images(fit_data, correction_data, stddev_data, fit_max):
            if irradiance_map is None:
                _irradiance_map = fit_data*fit_max
            else:
                _irradiance_map = irradiance_map

            log.info(f"\tSaving images...")
            # save std dev image
            tmp = stddev_data/_irradiance_map*255
            uint16_array = np.round(tmp).astype(np.uint8)
            image = Image.fromarray(uint16_array, mode='L')  # 'L' mode for grayscale
            image.save(str(directory / save_directory_name / 'stddev grid fit px.png'))
            
            tmp = 32767*stddev_data/np.max(stddev_data)
            tmp[0,0] = 65535
            tmp[0,1] = 0
            uint16_array = tmp.astype(np.uint16)
            image = Image.fromarray(uint16_array, mode='I;16')  # 'L' mode for grayscale
            image.save(str(directory / save_directory_name / 'stddev grid fit normalized.png'))
            
            tmp = stddev_data*1000
            uint16_array = tmp.astype(np.uint16)
            image = Image.fromarray(uint16_array, mode='I;16')  # 'L' mode for grayscale
            image.save(str(directory / save_directory_name / 'stddev grid fit mW.png'))

            # save 16-bit scan image
            tmp = fit_data*255
            uint16_array = np.round(tmp).astype(np.uint8)
            image = Image.fromarray(uint16_array, mode='L')  # 'L' mode for grayscale
            image.save(str(directory / save_directory_name / 'grid fit px.png'))

            tmp = 32767*fit_data/np.max(fit_data)
            tmp[0,0] = 65535
            tmp[0,1] = 0
            uint16_array = tmp.astype(np.uint16)
            image = Image.fromarray(uint16_array, mode='I;16')  # 'L' mode for grayscale
            image.save(str(directory / save_directory_name / 'grid fit normalized.png'))

            tmp = fit_data*fit_max*1000
            uint16_array = tmp.astype(np.uint16)
            image = Image.fromarray(uint16_array, mode='I;16')  # 'L' mode for grayscale
            image.save(str(directory / save_directory_name / 'grid fit mW.png'))

            # save correction pngs
            if light_correction:
                tmp = 255*correction_data  # for light correction
                uint8_array = np.round(tmp).astype(np.uint8)
                image = Image.fromarray(uint8_array, mode='L')  # 'L' mode for grayscale
                image.save(str(directory / save_directory_name / 'correction_image.png'))

        def compute_statistics(name, data, stats_df=None):
            if stats_df is None:
                stats_df = pd.DataFrame({
                    "name": pd.Series(dtype="object"),
                    "min": pd.Series(dtype="float"),
                    "max": pd.Series(dtype="float"),
                    "median": pd.Series(dtype="float"),
                    "mean": pd.Series(dtype="float"),
                    "range": pd.Series(dtype="float"),
                    "std": pd.Series(dtype="float")
                })
            stats = {
                "name": name,
                "min": np.min(data),
                "max": np.max(data),
                "median": np.median(data),
                "mean": np.mean(data),
                "range": np.ptp(data),
                "std": np.std(data)
            }
            # return stats_df.append(stats, ignore_index=True)
            return pd.concat([stats_df, pd.DataFrame([stats])], ignore_index=True)
        
        def save_statistics(stats_df):
            log.info(f"\tSaving stats...")
            stats_df.to_csv(str(directory / save_directory_name / "stats.csv"), index=False)

        def save_violin_plot(data, name, scale=None):
            plt.figure(figsize=(8, 6))
            plt.violinplot(data, showmeans=True)
            plt.title(f"Violin Plot of {name}")
            if scale is not None:
                plt.ylim(0, scale[1])
            plt.savefig(str(directory / save_directory_name / f"{name}_violin_plot.png"))
            plt.close()

        # create folders
        (directory / save_directory_name).mkdir(parents=True, exist_ok=True)

        # load csv
        irradiance_data = load_data()

        # convert to pixel space
        pixel_data = convert_to_pixel_space(irradiance_data)

        # create fit of data
        fit_data, stddev_data = map_data(pixel_data)

        # save stats (with and without 10px border)
        # Compute statistics for full images
        log.info(f"\tComputing stats...")
        stats_df = compute_statistics("irradiance", fit_data)
        stats_df = compute_statistics("sample_stddev", stddev_data, stats_df=stats_df)

        # Crop images by 10 pixels on each side and compute statistics
        fit_data_cropped = fit_data[10:-10, 10:-10]
        stddev_data_cropped = stddev_data[10:-10, 10:-10]

        stats_df = compute_statistics("irradiance_cropped_10", fit_data_cropped, stats_df=stats_df)
        stats_df = compute_statistics("sample_stddev_cropped_10", stddev_data_cropped, stats_df=stats_df)

        # Crop images by 100 pixels on each side and compute statistics
        fit_data_cropped2 = fit_data[100:-100, 100:-100]
        stddev_data_cropped2 = stddev_data[100:-100, 100:-100]

        stats_df = compute_statistics("irradiance_cropped_100", fit_data_cropped2, stats_df=stats_df)
        stats_df = compute_statistics("sample_stddev_cropped_100", stddev_data_cropped2, stats_df=stats_df)
        save_statistics(stats_df)

        # Generate violin plots
        log.info(f"\tSaving plots...")
        
        if irradiance_map is None:
            violin_min = np.min(fit_data)/1.1
            violin_max = np.max(fit_data)*1.1
        else:
            violin_min = np.min(irradiance_map)/1.1
            violin_max = np.max(irradiance_map)*1.1
        save_violin_plot(fit_data.flatten(), "irradiance", scale=(violin_min, violin_max))
        save_violin_plot(fit_data_cropped.flatten(), "irradiance_cropped_10", scale=(violin_min, violin_max))
        save_violin_plot(fit_data_cropped2.flatten(), "irradiance_cropped_100", scale=(violin_min, violin_max))

        # normalize data
        normalized_fit_data = normalize_data(fit_data)

        # make the correction data
        correction_data = create_correction_data(normalized_fit_data)
        
        # save correction image, std dev image, and scan image
        save_images(normalized_fit_data, correction_data, stddev_data, np.max(fit_data))

        return fit_data


    def capture_and_process_grayscale_correction(self):
        self.find_photodiode_center_and_focus()
        self.find_px_size()

        filename = "uncorrected_test_data.csv"
        self.measure_irradiance_grid2(fine=True, save_name = filename)
        save_directory_name = "uncorrected"
        irradiance_map = self._createCorrectionImage(filename, save_directory_name, None)

        filename = "corrected_test_data.csv"
        self.measure_irradiance_grid2(fine=True, save_name = filename)
        scale_factor = 1.0 # used if normalization factor was changed...
        save_directory_name = "corrected"
        self._createCorrectionImage(filename, save_directory_name, irradiance_map/scale_factor)