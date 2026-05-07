import os
import time
import json
import math
import stat
import shutil
import logging

import numpy as np
import pandas as pd
from PIL import Image
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from scipy.interpolate import griddata

from printer_server.settings import Config
import printer_server.views.home as home
from printer_server.settings import Config
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.printer_control.print_control import PrintControl
from printer_server.hardware_configuration.hardware_configuration import config_dict
from printer_server.views.calibration import (
    get_last_calibration_positions_from_logs, write_to_position_log
)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# sample_rate_hz = 1/300
# time_to_process = 0.0033

plt.rcParams.update({
    'font.size': 30,         # Base font size for most text
    'axes.titlesize': 36,    # Title size
    'axes.labelsize': 30,    # X and Y axis labels
    'xtick.labelsize': 30,   # X tick labels
    'ytick.labelsize': 30,   # Y tick labels
    'legend.fontsize': 36,   # Legend text
})

class TestControl(PrintControl):
    def test_worker(self):
        self.tmp_photodiode_focus = self.coord_systems["fiber_visitech"]["Focus"]
        self.printing_stopped.clear()

        funcs = self.print_settings["Functions"]
        counted = [fd for fd in funcs if fd["name"] not in {"setup_tests", "cleanup_tests"}]
        num_tests = len(counted)
        j = 0
        for f_dict in funcs:
            f_name = f_dict["name"]
            f = getattr(self, f_name, None)
            if f is None:
                log.error(f"Function '{f_name}' not found in {self.__class__.__name__}")
                continue

            kwargs = dict(f_dict.get("kwargs", {}))
            if f_name in {"setup_tests", "cleanup_tests"}:
                f()
            else:
                start = 100 * j / num_tests
                end   = 100 * (j + 1) / num_tests
                kwargs["progress"] = (start, end)
                f(**kwargs)
                j += 1

            if self.printing_stopped.is_set():
                break

        self.finish_print()

    def _update_progress(self, index, total, progress):
        percent = progress[0] + (progress[1]-progress[0])*index/total
        msg = {
            "percent": int(percent),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }
        home.update_printer_state("print progress", msg)

    def _subdivide_progress(self, index, count, progress):
        progress_range = progress[1]-progress[0]
        progress_subrange = progress_range/count
        start = progress[0]+index*progress_subrange
        end = progress[0]+(index+1)*progress_subrange
        return(start, end)
        
    def setup_tests(self):
        self.pre_print_tasks()
        self.pre_print_joins()

        # Setup
        self.photodiode.set_wavelength(365)
        self.photodiode.set_num_averages(2)
        self.photodiode.zero()

        self.light_engine = "visitech"
        self.light_engine_alignment = self.light_engines[self.light_engine].config_dict["orientation"]
        self.led_num = 0
        self.screen.setCorrectionEnable(False, light_engine=self.light_engine)

    def cleanup_tests(self):
        self.post_print_tasks()
        self.post_print_joins()

        # Reset photodiode averages
        self.photodiode.set_num_averages(self.photodiode.defaultAverages)

    def measure_keyence_line(self, step_size=0.15, scan_length_mm=25, number_of_scans=3, scan_spacing_mm=2.0, y_offset_mm=0.0, progress=(0,100)):
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

        self._update_progress(0, 1, progress)

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

                self._update_progress(len(x_set)*y_index+x_index+1, len(x_set)*len(y_set), progress)

    def find_photodiode_position_and_focus(self, position="center", initial_positioning=False, rough_pass=True, log_file="xyz_test_data.csv", progress=(0,100)):
        # initial positioning

        r_img_1 = "v_150px_vert_cent.png"
        r_img_2 = "v_150px_horz_cent.png"
        f_img_1 = "v_14px_vert.png"
        f_img_2 = "v_14px_horz.png"
        f_img_3 = "v_4px_vert.png"
        f_img_4 = "v_4px_horz.png"

        if position == "-x":
            r_img_1 = "v_150px_vert_right.png"
        elif position == "+x":
            r_img_1 = "v_150px_vert_left.png"
        elif position == "-y":
            r_img_2 = "v_150px_horz_top.png"
        elif position == "+y":
            r_img_2 = "v_150px_horz_bottom.png"
        elif position == "corner":
            self._find_photodiode_position(
                initial_positioning=False, 
                rough_pass=rough_pass,
                log_file=log_file, 
                orders=["X", "Y", "X", "Y"], 
                step_sizes=[0.01, 0.01, 0.0025, 0.0025], 
                step_counts=[20, 20, 20, 20], 
                images=[["v_4px.png"], ["v_4px.png"], ["v_4px.png"], ["v_4px.png"]], 
                use_find_peaks=[False, False, False, False], 
                use_fits=[False, False, True, True], 
                adjust_coords=[False, False, False, False], 
                use_positions=[True, True, True, True], 
                progress=progress
            )
            return
        elif position != "center":
            log.warning("Invalid position (%s) in find_photodiode_position_and_focus", position)

        
        if self.light_engine_alignment == "Y":
            tmp = r_img_1
            r_img_1 = r_img_2
            r_img_2 = tmp
            tmp = f_img_1
            f_img_1 = f_img_2
            f_img_2 = tmp
            tmp = f_img_3
            f_img_3 = f_img_4
            f_img_4 = tmp

        self._find_photodiode_position(
            initial_positioning=initial_positioning, 
            rough_pass=rough_pass,
            log_file=log_file,
            orders=["X","Y","X","Y","Focus","X","Y","Focus","X","Y","Focus","X","Y","Focus"], 
            step_sizes=[1.0,1.0,0.1,0.1,0.25,0.01,0.01,0.025,0.001,0.001,0.0025,0.001,0.001,0.0025], 
            step_counts=[20,20,20,20,40,20,20,50,20,20,50,20,20,50], 
            images=[
                [r_img_1],
                [r_img_2],
                [f_img_1],
                [f_img_2],
                ["v_14px_cross.png"],
                [f_img_3],
                [f_img_4],
                ["v_4px_cross.png"],
                ["v_1px_ring_inside.png"],
                ["v_1px_ring_inside.png"],
                ["v_2px_ring_inside.png","v_2px_ring_outside.png"],
                ["v_1px_ring_inside.png"],
                ["v_1px_ring_inside.png"],
                ["v_2px_ring_inside.png","v_2px_ring_outside.png"]
            ], 
            use_find_peaks=[False for _ in range(14)], 
            use_fits=[False,False,False,False,True,False,False,True,False,False,True,False,False,True], 
            adjust_coords=[position == "center" for _ in range(14)],
            use_positions=[True for _ in range(14)],
            progress=progress
        )

    def _excel_like_polyfit(self, x, y, degree):
        x = np.array(x, dtype=float)
        y = np.array(y, dtype=float)

        x_mean = x.mean()
        x_scale = (x.max() - x.min()) / 2
        if x_scale == 0:
            raise ValueError("All x values are identical; can't scale.")

        # Center and scale
        x_scaled = (x - x_mean) / x_scale
        coeffs_scaled = np.polyfit(x_scaled, y, degree)
        p_scaled = np.poly1d(coeffs_scaled)

        # Convert back to original x coefficients
        p_original = np.poly1d([0])
        for i, c in enumerate(coeffs_scaled):
            power = degree - i
            term = np.poly1d([1 / x_scale, -x_mean / x_scale]) ** power
            p_original += c * term

        def poly(x_new):
            return p_scaled((x_new - x_mean) / x_scale)

        return poly, coeffs_scaled, p_original.coefficients, (x_mean, x_scale)

    def _find_photodiode_position(self, initial_positioning=True, rough_pass=True, log_file="photodiode_focus.csv", orders=[], step_sizes=[], step_counts=[], images=[], use_find_peaks=[], use_fits=[], adjust_coords=[], use_positions=[], progress=(0,100)):
        self.test_log = str(self.current_job / "logs" / log_file)

        xy_threads = None
        focus_thread = None
        screen_thread = None

        step = 0
        self._update_progress(step, sum(step_counts), progress)

        # Move to rough position
        if initial_positioning:
            x_pos = self.coord_systems["fiber_visitech"]["X"]
            y_pos = self.coord_systems["fiber_visitech"]["Y"]
            z_pos = self.coord_systems["fiber_visitech"]["Focus"]
            focus_thread = self.focus_stage.threadedFocusMove(log, mm=z_pos, join=False)
            time.sleep(0.05)
            xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False)
        else:
            x_pos = self.xy_stage.getXYPosition(axis='X')
            y_pos = self.xy_stage.getXYPosition(axis='Y')
            z_pos = self.focus_stage.getFocusPosition()
        
        self.light_engines[self.light_engine].setup_exposure(1000, led_power=100, repeat=0, is_grayscale_corrected=False, led_num=self.led_num)
        self.light_engines[self.light_engine].perform_exposure()

        if initial_positioning:
            for thread in xy_threads:
                if thread is not None:
                    thread.join()
                    thread = None
            if focus_thread is not None:
                focus_thread.join()
                focus_thread = None

        for stage, step_size, step_count, image, _use_find_peaks, use_fit, adjust_coord, use_position in zip(orders, step_sizes, step_counts, images, use_find_peaks, use_fits, adjust_coords, use_positions):
            if step_size >= 0.1 and not rough_pass:
                continue
            
            if self.printing_stopped.is_set():
                return

            if stage == "X":
                x_pos = round(x_pos/step_size)*step_size
            if stage == "Y":
                y_pos = round(y_pos/step_size)*step_size
            if stage == "Z":
                z_pos = round(z_pos/step_size)*step_size
            
            # Draw image
            screen_thread = Thread(
                log, name="screen_draw_thread", target=self.screen.draw, args=[Path(Config.PRINT_SERVER_FOLDER) / "drivers" / self.light_engine / "images" / image[0]], kwargs={"light_engine": self.light_engine, "led_num": self.led_num}
            )
            screen_thread.start()
            irr_list = []
            irr_list2 = []
            pos_list = []

            # Move to start
            if stage == "X" or stage == "Y":
                if stage == "X":
                    pos = x_pos - step_count*step_size/2
                    xy_threads = self.xy_stage.threadedXYMove(log, pos, None, join=False)
                else:
                    pos = y_pos - step_count*step_size/2
                    xy_threads = self.xy_stage.threadedXYMove(log, None, pos, join=False)
            else:
                pos = z_pos - step_count*step_size/2
                focus_thread = self.focus_stage.threadedFocusMove(log, mm=pos, join=False)
                time.sleep(0.05)
                if self.focus_stage.config_dict.get("link_focus_and_y_movement", False):
                    xy_threads = self.xy_stage.threadedXYMove(log, None, y_pos, join=False)

            for thread in xy_threads:
                if thread is not None:
                    thread.join()
                    thread = None
            if focus_thread is not None:
                focus_thread.join()
                focus_thread = None
            if screen_thread is not None:
                screen_thread.join()
                screen_thread = None

            # Measure power
            time.sleep(0.25)
            pos_list.append(pos)
            irr_list.append(self.photodiode.get_power_density())
            if len(image) > 1:
                self.screen.draw(Path(Config.PRINT_SERVER_FOLDER) / "drivers" / self.light_engine / "images" / image[1], light_engine=self.light_engine, led_num=self.led_num)
                irr_list2.append(self.photodiode.get_power_density())
                screen_thread = Thread(
                    log, name="screen_draw_thread", target=self.screen.draw, args=[Path(Config.PRINT_SERVER_FOLDER) / "drivers" / self.light_engine / "images" / image[0]], kwargs={"light_engine": self.light_engine, "led_num": self.led_num}
                )
                screen_thread.start()
            for i in range(step_count):
                # Step stage
                pos += step_size
                if stage in ["X", "Y"]:
                    self.xy_stage.threadedXYMove(log, pos if stage == "X" else None, pos if stage == "Y" else None, join=True)
                else:
                    focus_thread = self.focus_stage.threadedFocusMove(log, mm=pos, join=False)
                    time.sleep(0.05)
                    if self.focus_stage.config_dict.get("link_focus_and_y_movement", False):
                        self.xy_stage.threadedXYMove(log, None, y_pos, join=True)
                    if focus_thread is not None:
                        focus_thread.join()

                # Measure power
                time.sleep(0.05)
                if screen_thread is not None:
                    screen_thread.join()
                    screen_thread = None
                pos_list.append(pos)
                irr_list.append(self.photodiode.get_power_density())
                if len(image) > 1:
                    self.screen.draw(Path(Config.PRINT_SERVER_FOLDER) / "drivers" / self.light_engine / "images" / image[1], light_engine=self.light_engine, led_num=self.led_num)
                    irr_list2.append(self.photodiode.get_power_density())
                    screen_thread = Thread(
                        log, name="screen_draw_thread", target=self.screen.draw, args=[Path(Config.PRINT_SERVER_FOLDER) / "drivers" / self.light_engine / "images" / image[0]], kwargs={"light_engine": self.light_engine, "led_num": self.led_num}
                    )
                    screen_thread.start()

                if self.printing_stopped.is_set():
                    return

                step += 1
                self._update_progress(step, sum(step_counts), progress)

            pos -= step_count*step_size

            if len(image) > 1:
                # Log peak
                log.info(pos_list)
                log.info(irr_list)
                log.info(irr_list2)
                irr_list = [p1-p2 for p1, p2 in zip(irr_list, irr_list2)]

            # find peak
            if use_fit:
                polynomial, coefficients_1, coefficients_2, (x_mean, x_scale) = self._excel_like_polyfit(pos_list, irr_list, 5)
                log.info(coefficients_1)
                log.info(coefficients_2)
                fit_list = polynomial(pos_list)
                fit_list = fit_list.tolist()
                if _use_find_peaks:
                    max_val = min(fit_list)
                else:
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
            if use_position:
                if stage == "X":
                    x_pos = peak_pos
                    if adjust_coord:
                        self.coord_systems["fiber_visitech"][stage] = x_pos
                elif stage == "Y":
                    y_pos = peak_pos
                    if adjust_coord:
                        self.coord_systems["fiber_visitech"][stage] = y_pos
                elif stage == "Focus":
                    z_pos = peak_pos
                    if adjust_coord:
                        self.tmp_photodiode_focus = z_pos
            if stage == "X":
                xy_threads = self.xy_stage.threadedXYMove(log, x_pos, None, join=False)
            if stage == "Y":
                xy_threads = self.xy_stage.threadedXYMove(log, None, y_pos, join=False)
            else:
                focus_thread = self.focus_stage.threadedFocusMove(log, mm=z_pos, join=False)
                time.sleep(0.05)
                if self.focus_stage.config_dict.get("link_focus_and_y_movement", False):
                    self.xy_stage.threadedXYMove(log, None, y_pos, join=False)  


            for thread in xy_threads:
                if thread is not None:
                    thread.join()
                    thread = None
            if focus_thread is not None:
                focus_thread.join()
                focus_thread = None

            # Log peak
            log.info(pos_list)
            log.info(irr_list)
            if use_fit:
                log.info(fit_list)

            # time.sleep(0.1)

            async_file_hander.write(self.test_log, f"{pos_list}\n")
            async_file_hander.write(self.test_log, f"{irr_list}\n")
            if use_fit:
                async_file_hander.write(self.test_log, f"{fit_list}\n")
            async_file_hander.write(self.test_log, f"X:{self.xy_stage.getXYPosition(axis='X'):.3f} Y:{self.xy_stage.getXYPosition(axis='Y'):.3f} Z:{self.focus_stage.getFocusPosition()}\n")
            async_file_hander.write(self.test_log, f"\n")

        self.light_engines[self.light_engine].stop_sequencer()

    # Measures the 4 corners to find out the exact pixel size in x and y
    def _find_px_size(self, progress=(0,100)):
        if self.light_engine_alignment == "X":
            x_px = 2560
            y_px = 1600
        else:
            x_px = 1600
            y_px = 2560
        
        x_px_size = 0.00756
        y_px_size = 0.00756

        focus_spot_px = 4

        self._update_progress(0, 4, progress)

        # Find 4 corners
        x_pos = self.coord_systems["fiber_visitech"]["X"] - (x_px-focus_spot_px)*x_px_size/2
        y_pos = self.coord_systems["fiber_visitech"]["Y"] - (y_px-focus_spot_px)*y_px_size/2
        self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=True)
        # self.find_photodiode_position_and_focus(find_corners=True, progress=self._subdivide_progress(0,4,progress))
        self.find_photodiode_position_and_focus(position="corner", rough_pass=True, log_file="xyz_test_data.csv", progress=self._subdivide_progress(0,4,progress))
        x1 = self.xy_stage.getXYPosition(axis="X")
        y1 = self.xy_stage.getXYPosition(axis="Y")
        if self.printing_stopped.is_set():
            return
        
        x_pos = self.coord_systems["fiber_visitech"]["X"] - (x_px-focus_spot_px)*x_px_size/2
        y_pos = self.coord_systems["fiber_visitech"]["Y"] + (y_px-focus_spot_px)*y_px_size/2
        self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=True)
        # self.find_photodiode_position_and_focus(find_corners=True, progress=self._subdivide_progress(1,4,progress))
        self.find_photodiode_position_and_focus(position="corner", rough_pass=True, log_file="xyz_test_data.csv", progress=self._subdivide_progress(1,4,progress))
        x2 = self.xy_stage.getXYPosition(axis="X")
        y2 = self.xy_stage.getXYPosition(axis="Y")
        if self.printing_stopped.is_set():
            return
        
        x_pos = self.coord_systems["fiber_visitech"]["X"] + (x_px-focus_spot_px)*x_px_size/2
        y_pos = self.coord_systems["fiber_visitech"]["Y"] + (y_px-focus_spot_px)*y_px_size/2
        self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=True)
        # self.find_photodiode_position_and_focus(find_corners=True, progress=self._subdivide_progress(2,4,progress))
        self.find_photodiode_position_and_focus(position="corner", rough_pass=True, log_file="xyz_test_data.csv", progress=self._subdivide_progress(2,4,progress))
        x3 = self.xy_stage.getXYPosition(axis="X")
        y3 = self.xy_stage.getXYPosition(axis="Y")
        if self.printing_stopped.is_set():
            return

        x_pos = self.coord_systems["fiber_visitech"]["X"] + (x_px-focus_spot_px)*x_px_size/2
        y_pos = self.coord_systems["fiber_visitech"]["Y"] - (y_px-focus_spot_px)*y_px_size/2
        self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=True)
        # self.find_photodiode_position_and_focus(find_corners=True, progress=self._subdivide_progress(3,4,progress))
        self.find_photodiode_position_and_focus(position="corner", rough_pass=True, log_file="xyz_test_data.csv", progress=self._subdivide_progress(3,4,progress))
        x4 = self.xy_stage.getXYPosition(axis="X")
        y4 = self.xy_stage.getXYPosition(axis="Y")
        if self.printing_stopped.is_set():
            return

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
    # Should run find_photodiode_position_and_focus and _find_px_size first
    def _measure_irradiance_grid(self, fine=True, save_name = "test_data.csv", correction_path="", test=False, progress=(0,100)):
        if self.printing_stopped.is_set():
            return

        ################ Step ################
        # Setup file
        test_log = str(self.current_job / "logs" / save_name)
        async_file_hander.write(
                test_log, "time,irradiance,x,y,\n"
            )

        x_px = 2560
        y_px = 1600
        if fine:
            # note: 15 & 30 are both factors of both 1590 and 2550 (our spot is 10px, so - 5 from each side)
            x_steps = 30
            y_steps = 30
            # x_steps = 15
            # y_steps = 15
            # x_steps = 51
            # y_steps = 53
        else:
            # note: 150 and 159 are factors of 2550 and 1590 respectively
            x_steps = 150
            y_steps = 159
            # x_steps = 510
            # y_steps = 530
        
        if self.light_engine_alignment == "Y":
            tmp = x_px
            x_px = y_px
            y_px = tmp

            tmp = x_steps
            x_steps = y_steps
            y_steps = tmp
            
        x_range = range(5, x_px, x_steps)
        y_range = range(5, y_px, y_steps)

        self._update_progress(0, len(x_range)*len(y_range), progress)

        self.light_engines[self.light_engine].setup_exposure(1000, led_power=100, repeat=0, is_grayscale_corrected=(correction_path != ""), led_num=self.led_num)
        self.light_engines[self.light_engine].perform_exposure()
        
        if test:
            image = Image.open(Path(Config.PRINT_SERVER_FOLDER) / "drivers" / self.light_engine / "images" / "demarked.png") # Used to check orientation
        else:
            image = Image.open(Path(Config.PRINT_SERVER_FOLDER) / "drivers" / self.light_engine / "images" / "white.png")

        if correction_path != "":
            mask = image
            correction = Image.open(correction_path)
            image = Image.composite(correction, mask, mask=mask)
        image.save(self.current_job / self.print_settings["Header"]["Image directory"] / f"temp.png")  # Saves the image
        # Draw correction image
        self.screen.draw(self.current_job / self.print_settings["Header"]["Image directory"] / f"temp.png", light_engine=self.light_engine, led_num=self.led_num)

        for x_index, x in enumerate(x_range):
            for y_index, y in enumerate(y_range):
                # Move to location
                x_pos = self.coord_systems["fiber_visitech"]["X"] + (x - x_px/2)*self.x_px_size
                y_pos = self.coord_systems["fiber_visitech"]["Y"] + (y - y_px/2)*self.y_px_size
                self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=True)

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

                self._update_progress(x_index*len(y_range)+y_index+1, len(x_range)*len(y_range), progress)

        self.light_engines[self.light_engine].stop_sequencer()

    def _createCorrectionImage(self, filename, save_directory_name, irradiance_map, light_correction=True, remove_outliers=True, grayscale_min=0.75):
        directory = self.current_job / "logs"
        light_engine_resolution = self.light_engines[self.light_engine].config_dict["resolution"]
        x_pixels = light_engine_resolution[0]
        y_pixels = light_engine_resolution[1]
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

            # Swap axis (pixel_data, height/width, pitch, offsets) if Y orientation
            if self.light_engine_alignment == "Y":
                physical_height = self.x_px_size*y_pixels
                physical_width = self.y_px_size*x_pixels

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
            else:
                physical_height = self.y_px_size*y_pixels
                physical_width = self.x_px_size*x_pixels

                pixel_data = np.array([irradiance_data[0, :], irradiance_data[1, :], irradiance_data[2, :], irradiance_data[3, :]])
                _x_pixel_pitch = self.x_px_size
                _y_pixel_pitch = self.y_px_size

                pixel_data[0, :] = (pixel_data[0, :] + physical_width/2 - x_offset) / _x_pixel_pitch
                pixel_data[1, :] = (pixel_data[1, :] + physical_height/2 - y_offset) / _y_pixel_pitch

            # Mirror axis if needed
            if self.light_engine_alignment == "Y": # HR5/HR3v3
                pixel_data[1, :] = (-pixel_data[1, :] + y_pixels)
            else: # MR1/OS1
                pass

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
            
            # tmp = 32767*stddev_data/np.max(stddev_data)
            # tmp[0,0] = 65535
            # tmp[0,1] = 0
            # uint16_array = tmp.astype(np.uint16)
            # image = Image.fromarray(uint16_array, mode='I;16')  # 'L' mode for grayscale
            # image.save(str(directory / save_directory_name / 'stddev grid fit normalized.png'))
            
            tmp = stddev_data*1000
            uint16_array = tmp.astype(np.uint16)
            image = Image.fromarray(uint16_array, mode='I;16')  # 'L' mode for grayscale
            image.save(str(directory / save_directory_name / 'stddev grid fit mW.png'))

            # save 16-bit scan image
            tmp = fit_data*255
            uint16_array = np.round(tmp).astype(np.uint8)
            image = Image.fromarray(uint16_array, mode='L')  # 'L' mode for grayscale
            image.save(str(directory / save_directory_name / 'grid fit px.png'))

            # tmp = 32767*fit_data/np.max(fit_data)
            # tmp[0,0] = 65535
            # tmp[0,1] = 0
            # uint16_array = tmp.astype(np.uint16)
            # image = Image.fromarray(uint16_array, mode='I;16')  # 'L' mode for grayscale
            # image.save(str(directory / save_directory_name / 'grid fit normalized.png'))

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
            plt.figure(figsize=(16, 12))
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
        save_violin_plot(fit_data.flatten(), f"{save_directory_name.capitalize()} Irradiance", scale=(violin_min, violin_max))
        save_violin_plot(fit_data_cropped.flatten(), f"{save_directory_name.capitalize()} Irradiance_cropped_10", scale=(violin_min, violin_max))
        save_violin_plot(fit_data_cropped2.flatten(), f"{save_directory_name.capitalize()} Irradiance_cropped_100", scale=(violin_min, violin_max))

        # normalize data
        normalized_fit_data = normalize_data(fit_data)

        # make the correction data
        correction_data = create_correction_data(normalized_fit_data)
        
        # save correction image, std dev image, and scan image
        save_images(normalized_fit_data, correction_data, stddev_data, np.max(fit_data))

        return fit_data

    def capture_and_process_grayscale_correction(self, fine=True, save_results=True, orientation_test=False, find_focus=True, progress=(0,100)):
        x_pos = self.coord_systems["fiber_visitech"]["X"]
        y_pos = self.coord_systems["fiber_visitech"]["Y"]
        z_pos = self.tmp_photodiode_focus
        focus_thread = self.focus_stage.threadedFocusMove(log, mm=z_pos, join=False)
        time.sleep(0.05)
        xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False)

        for thread in xy_threads:
            if thread is not None:
                thread.join()
                thread = None
        if focus_thread is not None:
            focus_thread.join()
            focus_thread = None

        # Find the center and focus of the photodiode
        self._update_progress(0, 4, progress)
        # self.x_px_size = 0.00756
        # self.y_px_size =  0.00756
        if find_focus:
            self.find_photodiode_position_and_focus(progress=self._subdivide_progress(0,6,progress))
        if self.printing_stopped.is_set():
            return
        self._find_px_size(progress=self._subdivide_progress(1,6,progress))

        # Measure the irradiance grid without correction to use as the basis for the correction image
        filename = "uncorrected_test_data.csv"
        self._measure_irradiance_grid(fine=fine, save_name=filename, test=orientation_test, progress=self._subdivide_progress(2,6,progress))
        if self.printing_stopped.is_set():
            return
        save_directory_name = "uncorrected"
        irradiance_map = self._createCorrectionImage(filename, save_directory_name, None)

        if not orientation_test:
            # Measure the grid with/without normalization to calculate the visitech normalization factor
            old_grayscale_normalization_factors = self.light_engines[self.light_engine].config_dict["grayscale_normalization_factor"].copy() if "grayscale_normalization_factor" in self.light_engines[self.light_engine].config_dict.keys() else None

            if "grayscale_normalization_factor" not in self.light_engines[self.light_engine].config_dict.keys():
                self.light_engines[self.light_engine].config_dict["grayscale_normalization_factor"] = self.light_engines[self.light_engine].config_dict["normalization_factor"].copy()
            else:
                self.light_engines[self.light_engine].config_dict["grayscale_normalization_factor"][self.led_num] = self.light_engines[self.light_engine].config_dict["normalization_factor"][self.led_num]
            filename = "corrected_nonnormalized_test_data.csv"
            self._measure_irradiance_grid(fine=False, save_name=filename, correction_path=str(self.current_job / 'logs/uncorrected/correction_image.png'), progress=self._subdivide_progress(3,6,progress))
            save_directory_name = "corrected_nonnormalized"
            nonnormalized_irradiance_map = self._createCorrectionImage(filename, save_directory_name, None)
            self.light_engines[self.light_engine].config_dict["grayscale_normalization_factor"][self.led_num] = round(self.light_engines[self.light_engine].config_dict["grayscale_normalization_factor"][self.led_num]*np.mean(irradiance_map)/np.mean(nonnormalized_irradiance_map),3)
            filename = "corrected_normalized_test_data.csv"
            self._measure_irradiance_grid(fine=False, save_name=filename, correction_path=str(self.current_job / 'logs/uncorrected/correction_image.png'), progress=self._subdivide_progress(4,6,progress))
            save_directory_name = "corrected_normalized"
            normalized_irradiance_map = self._createCorrectionImage(filename, save_directory_name, None)
            log.info("Pre mean irradiance: %s, Post mean irradiance: %s, Updated to: %s", np.mean(irradiance_map), np.mean(nonnormalized_irradiance_map), np.mean(normalized_irradiance_map))

        # Now measure the grid with the correction to see the improvement
        filename = "corrected_test_data.csv"
        correction_img = self.current_job / "logs/uncorrected/correction_image.png"
        self._measure_irradiance_grid(fine=fine, save_name=filename, correction_path=str(correction_img), test=orientation_test, progress=self._subdivide_progress(5,6,progress))
        if self.printing_stopped.is_set():
            return
        scale_factor = 1.0  # used if normalization factor was changed...
        save_directory_name = "corrected"
        final_irradiance_map = self._createCorrectionImage(filename, save_directory_name, irradiance_map/scale_factor)

        # Combine datasets for global min/max and histogram
        combined_fit_data = np.concatenate([irradiance_map.flatten(), final_irradiance_map.flatten()])

        # Compute global min and max for grayscale mapping
        global_min = np.min(combined_fit_data)
        global_max = np.max(combined_fit_data)

        # Save grayscale remapped 8-bit images for both datasets
        def save_remapped_grayscale(data, save_path, vmin, vmax):
            # Clip and normalize
            clipped = np.clip(data, vmin, vmax)
            normalized = ((clipped - vmin) / (vmax - vmin) * 255).astype(np.uint8)
            img = Image.fromarray(normalized, mode='L')
            img.save(save_path)

        save_remapped_grayscale(irradiance_map,
                                self.current_job / "logs" / "uncorrected" / "grid fit remapped.png",
                                global_min, global_max)

        save_remapped_grayscale(final_irradiance_map,
                                self.current_job / "logs" / "corrected" / "grid fit remapped.png",
                                global_min, global_max)

        def plot_histogram_dual_yaxis(uncorrected, corrected, out_path, min_val, max_val):
            """
            Plot histogram with:
            - Primary Y-axis = pixel count
            - Secondary Y-axis = piecewise function for remap to 8-bit gray levels.
            - Zoomed option centers around [min_val, max_val] with margin
            """
            span = max_val - min_val
            margin = span * 0.05
            x_min = min_val - margin
            x_max = max_val + margin

            fig, ax1 = plt.subplots(figsize=(20, 12))
            bins = np.linspace(x_min, x_max, 256)

            # Histograms for both images
            ax1.hist(uncorrected, bins=bins, alpha=0.6, color='blue', edgecolor='black', label='Uncorrected')
            ax1.hist(corrected, bins=bins, alpha=0.6, color='red', edgecolor='black', label='Corrected')

            ax1.set_xlabel("Irradiance (mW/cm²)")
            ax1.set_ylabel("Pixel Count")
            ax1.set_title("Grayscale Mapping for Uncorrected and Corrected Data")
            ax1.legend(loc="upper left")

            # Secondary Y-axis: piecewise mapping
            ax2 = ax1.twinx()

            # Define piecewise function for visualization
            x_vals = np.linspace(x_min, x_max, 500)  # μW/cm²
            gray_vals = np.piecewise(
                x_vals,
                [x_vals < min_val, (x_vals >= min_val) & (x_vals <= max_val), x_vals > max_val],
                [0, lambda x: (x - min_val) / (max_val - min_val) * 255, 255]
            )

            ax2.plot(x_vals, gray_vals, color='green', linewidth=2, label="Gray Level Mapping")
            ax2.set_ylabel("Gray Level (0-255)")
            ax2.set_ylim(0, 255)
            ax2.legend(loc="upper right")

            plt.xlim(x_min, x_max)
            plt.tight_layout()
            plt.savefig(out_path, dpi=300)
            plt.close()

        plot_histogram_dual_yaxis(irradiance_map.flatten(), final_irradiance_map.flatten(), self.current_job / "logs" / "histogram.png", global_min, global_max)

        shutil.copy(self.current_job / 'logs/uncorrected/correction_image.png', self.current_job / 'logs/correction_image.png')

        if not save_results and not orientation_test:
            # restore previous normalization factor if we aren't saving results
            if old_grayscale_normalization_factors is not None:
                self.light_engines[self.light_engine].config_dict["grayscale_normalization_factor"] = old_grayscale_normalization_factors
            else:
                del self.light_engines[self.light_engine].config_dict["grayscale_normalization_factor"]
        if save_results:
            # --- persist the corrected correction image with a single timestamp used everywhere ---
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_dir = Path(Config.PRINT_SERVER_FOLDER) / "grayscale_correction_data"
            correction_image_name = f"{Config.HOSTNAME}_corrected_{ts}.png"

            shutil.copy(correction_img, dest_dir / correction_image_name)

            # --- update hardware configuration JSON with the grayscale correction path ---
            # locate the host-specific config JSON
            cfg_path = next(
                (Path(Config.PRINT_SERVER_FOLDER) / "hardware_configuration").rglob(f"{Config.HOSTNAME}.json")
            )
            stat_info = cfg_path.stat()
            uid, gid = stat_info.st_uid, stat_info.st_gid
            mode = stat_info.st_mode

            # load, update the known field, and atomically write back
            with open(cfg_path, "r", encoding="utf-8") as fh:
                cfg = json.load(fh)

            # do we do this with multiple leds? if so, we need to add all of them, if not, we need to make sure the path is added at the right index
            cfg[self.light_engine]["light_grayscale_correction_image"] = [str(correction_image_name)]
            self.light_engines[self.light_engine].config_dict["light_grayscale_correction_image"] = str(correction_image_name)
            self.screen.config_dict[self.light_engine]["light_grayscale_correction_image"] = str(correction_image_name)

            tmp = cfg_path.with_suffix(cfg_path.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, cfg_path)
            os.chown(cfg_path, uid, gid)
            os.chmod(cfg_path, stat.S_IMODE(mode))
            log.info(f"Updated {cfg_path} with grayscale correction path: {correction_image_name}")

    # note update normalization and grayscale normalization

    def center_tip_tilt(self, progress=(0,100)):
        # move ttrf to center of motion
        tip_limits = self.ttr_stage.getTTRLimits("Tip")
        tilt_limits = self.ttr_stage.getTTRLimits("Tilt")
        focus_limits = self.focus_stage.getFocusLimits()
        ttr_threads = self.ttr_stage.threadedTTRMove(
            log,
            (tip_limits[1]-tip_limits[0])/2 + tip_limits[0],
            (tilt_limits[1]-tilt_limits[0])/2 + tilt_limits[0],
            None,
            join=False
        )
        self.focus_stage.threadedFocusMove(
            log,
            (focus_limits[1]-focus_limits[0])/2 + focus_limits[0],
            join=True
        )
        for thread in ttr_threads:
            if thread is not None:
                thread.join()
                if thread.exception is not None:
                    log.critical("Unable to move ttr stages")
                    self.failed_hardware["TTR Stage"] = self.ttr_stage
                    raise PrintingException()

        last_positions = get_last_calibration_positions_from_logs()
        last_positions[f"{self.light_engine}_focus_base"] = float(f"{(self.focus_stage.getFocusPosition())*1000:.1f}")
        last_positions[f"{self.light_engine}_tip_base"] = float(f"{(self.ttr_stage.getTTRPosition('Tip'))*1000:.1f}")
        # last_positions[f"{self.light_engine}_tilt_base"] = float(f"{(self.ttr_stage.getTTRPosition('Tilt'))*1000:.1f}")   
        write_to_position_log(last_positions)
    
    def keyence_tip_tilt_correction(self, axis="", iterations=4, check=True, rough_pass=True, measurement_distance=10000.0, progress=(0,100)):
        if axis == "Tilt":
            x, y = 0, measurement_distance / 1000 / 2
        elif axis == "Tip":
            x, y = -measurement_distance / 1000 / 2, 0
        else:
            raise ValueError("Axis must be either 'Tilt' or 'Tip'.")

        self.test_log = str(self.current_job / "logs" / f"keyence_{axis}.csv")

        step = 0
        if check:
            iterations += 1
        self._update_progress(step, 4, progress)
        x_pos = self.coord_systems["keyence_visitech"]["X"]
        y_pos = self.coord_systems["keyence_visitech"]["Y"]
        z_pos = self.coord_systems["keyence_visitech"]["Focus"]
        for i in range(iterations):
            keyence_readings = []
            for X , Y in [
                (-x, -y),
                (x, y),
            ]:
                focus_thread = self.focus_stage.threadedFocusMove(log, mm=z_pos, join=False)
                time.sleep(0.05)
                xy_threads = self.xy_stage.threadedXYMove(log, x_pos+X, y_pos+Y, join=False)
                if focus_thread is not None:
                    focus_thread.join()
                    focus_thread = None
                for thread in xy_threads:
                    if thread is not None:
                        thread.join()
                        thread = None
                        
                time.sleep(1.0)
                keyence_reading = self.keyence.read_sensor(self.light_engine)
                keyence_readings.append(keyence_reading)

                step += 1
                self._update_progress(step, iterations*2+2, progress)

                if self.printing_stopped.is_set():
                    return

            async_file_hander.write(self.test_log, f"{i}\n")
            log.info(f"-{axis} : {keyence_readings[0]}")
            async_file_hander.write(self.test_log, f"-{axis} : {keyence_readings[0]}\n")
            log.info(f"+{axis} : {keyence_readings[1]}")
            async_file_hander.write(self.test_log, f"+{axis} : {keyence_readings[1]}\n")
            diff = (keyence_readings[1] - keyence_readings[0])
            log.info(f"d{axis} average: {diff}")
            async_file_hander.write(self.test_log, f"d{axis} average: {diff}\n")

            offset = math.atan(diff / (measurement_distance))
            log.info(f"{axis} rad: {offset}")
            async_file_hander.write(self.test_log, f"{axis} rad: {offset}\n")
            # add difference to tilt stage position
            if not(check and i == iterations - 1):
                last_positions = get_last_calibration_positions_from_logs()
                curOffset = last_positions.get(f"{self.light_engine}_{axis.lower()}_base",0)/1000
                log.info(f"curOffset: {curOffset}")
                async_file_hander.write(self.test_log, f"curOffset: {curOffset}\n")
                log.info(f"New {axis} offset: {curOffset - offset}")
                async_file_hander.write(self.test_log, f"New {axis} offset: {curOffset - offset}\n")
                self.ttr_stage.threadedTTRMove(log, 
                                               curOffset - offset if axis == "Tip" else None,
                                               curOffset - offset if axis == "Tilt" else None,
                                               curOffset - offset if axis == "Rotate" else None,
                                               join=True)
                
                last_positions[f"{self.light_engine}_{axis.lower()}_base"] = float(f"{(curOffset - offset)*1000:.1f}")
                write_to_position_log(last_positions)
        async_file_hander.write(self.test_log, f"\n")

    def _spiral_until_threshold(self, step=5.0, photodiode_threshold=30.0):
        """
        Moves the stage in a square spiral in 'step' increments until photodiode exceeds threshold.
        """
        self.light_engines[self.light_engine].setup_exposure(1000, led_power=100, repeat=0, is_grayscale_corrected=False, led_num=self.led_num)
        self.light_engines[self.light_engine].perform_exposure()
        self.screen.draw(Path(Config.PRINT_SERVER_FOLDER) / "drivers" / self.light_engine / "images" / "white.png", light_engine=self.light_engine, led_num=self.led_num)
        time.sleep(0.05)

        x = self.xy_stage.getXYPosition(axis="X")
        y = self.xy_stage.getXYPosition(axis="Y")
        pos_list = [(x, y)]
        irr_list = [self.photodiode.get_power_density()]

        if irr_list[-1] >= photodiode_threshold:
            self.light_engines[self.light_engine].stop_sequencer()
            return pos_list, irr_list

        dx, dy = step, 0
        steps_in_leg = 1  # number of segments per leg
        leg_count = 0

        while irr_list[-1] < photodiode_threshold:
            for _ in range(2):  # two legs per spiral "ring"
                for _ in range(steps_in_leg):
                    x += dx
                    y += dy
                    self.xy_stage.threadedXYMove(log, x, y, join=True)
                    time.sleep(0.05)
                    pos_list.append((x, y))
                    irr_list.append(self.photodiode.get_power_density())
                    if irr_list[-1] >= photodiode_threshold:
                        self.light_engines[self.light_engine].stop_sequencer()
                        return pos_list, irr_list
                # rotate direction 90°
                dx, dy = -dy, dx
                leg_count += 1
            steps_in_leg += 1  # after two legs, increase leg length

    def photodiode_tip_tilt_correction(self, axis="", iterations=2, rough_pass=True, check=True, measurement_distance=10852.8, progress=(0,100)):
        if axis == "Tilt":
            x, y = 0, measurement_distance / 1000 / 2
        elif axis == "Tip":
            x, y = -measurement_distance / 1000 / 2, 0
        else:
            raise ValueError("Axis must be either 'Tilt' or 'Tip'.")

        if check:
            iterations += 1
        step = 0
        x_pos = self.coord_systems["fiber_visitech"]["X"]
        y_pos = self.coord_systems["fiber_visitech"]["Y"]
        z_pos = self.tmp_photodiode_focus
        for i in range(iterations):
            readings = []
            for X , Y in [
                (-x, -y),
                (x, y),
            ]:
                focus_thread = self.focus_stage.threadedFocusMove(log, mm=z_pos, join=False)
                time.sleep(0.05)
                xy_threads = self.xy_stage.threadedXYMove(log, x_pos-X, y_pos-Y, join=False)
                for thread in xy_threads:
                    if thread is not None:
                        thread.join()
                        thread = None
                if focus_thread is not None:
                    focus_thread.join()
                    focus_thread = None
                
                # spiral until we are on the image
                if rough_pass:
                    self._spiral_until_threshold()
                
                if axis == "Tilt":
                    if Y < 0:
                        position = "-y"
                    else:
                        position = "+y"
                else:
                    if X < 0:
                        position = "-x"
                    else:
                        position = "+x"

                self.find_photodiode_position_and_focus(position=position, rough_pass=True, log_file=f"photodiode_{axis}_{i}.csv", progress=self._subdivide_progress(step, (iterations*2), progress))
                reading = self.focus_stage.getFocusPosition()*1000
                readings.append(reading)
                step += 1

                if self.printing_stopped.is_set():
                    return

            self.test_log = str(self.current_job / "logs" / f"photodiode_{axis}_{i}.csv")
            log.info(f"-{axis} : {readings[0]}")
            async_file_hander.write(self.test_log, f"-{axis} : {readings[0]}\n")
            log.info(f"+{axis} : {readings[1]}")
            async_file_hander.write(self.test_log, f"+{axis} : {readings[1]}\n")
            diff = (readings[0] - readings[1])
            log.info(f"d{axis} average: {diff}")
            async_file_hander.write(self.test_log, f"d{axis} average: {diff}\n")

            offset = math.atan(diff / (measurement_distance))
            log.info(f"{axis} rad: {offset}")
            async_file_hander.write(self.test_log, f"{axis} rad: {offset}\n")

            if not(check and i == iterations - 1):
                # add difference to tilt stage position
                last_positions = get_last_calibration_positions_from_logs()
                curOffset = last_positions.get(f"{self.light_engine}_{axis.lower()}_base",0)/1000
                log.info(f"curOffset: {curOffset}")
                async_file_hander.write(self.test_log, f"curOffset: {curOffset}\n")
                log.info(f"New {axis} offset: {curOffset - offset}")
                async_file_hander.write(self.test_log, f"New {axis} offset: {curOffset - offset}\n")
                self.ttr_stage.threadedTTRMove(log, 
                                               curOffset - offset if axis == "Tip" else None,
                                               curOffset - offset if axis == "Tilt" else None,
                                               curOffset - offset if axis == "Rotate" else None,
                                               join=True)

                last_positions[f"{self.light_engine}_{axis.lower()}_base"] = float(f"{(curOffset - offset)*1000:.1f}")
                write_to_position_log(last_positions)