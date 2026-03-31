import time
import logging
from pathlib import Path
from datetime import datetime
from scipy.signal import find_peaks

import printer_server.views.home as home
from printer_server.settings import Config
from printer_server.threading_wrapper import Thread
from printer_server.print_file_validator import check_version
from printer_server.async_file_handler import async_file_hander
from printer_server.printer_control.print_control import PrintControl, PrintingException, run_in_thread
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles
from printer_server.views.calibration import (
    get_last_calibration_positions_from_logs, write_to_position_log
)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

ts = "%Y-%m-%d %H:%M:%S.%f"

class PhotodiodeFocusControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.light_engines = driver_handles.light_engines
        self.photodiode = driver_handles.photodiode
        self.focus_stage = driver_handles.focus_stage

        self.light_engine = "visitech"
        self.light_engine_alignment = self.light_engines[self.light_engine].config_dict["orientation"]
        self.led_num = 0

        self.calibration_positions = None

        self.photodiode_focus_log = str(self.current_job / "logs" / "photodiode_focus_data.csv")

    # Note photodiode in connected and initilized in light_measurement_control.py

    def create_logs(self):
        super().create_logs()

        async_file_hander.write(
            self.photodiode_focus_log,
            "time,data_type,data\n",
        )

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

    def pre_print_tasks(self):
        """
        Step-by-step procedure for pre-print photodiode sensor focus calibration:

        1. Get calibration positions from calibration position log
        2. Perform measurements for each light engine:
            a. move to measurement position
            b. run photodiode algorithm to find best focus
            c. calculate focus drift and move focus stage
            d. Update coordinate systems with new focus positions
        """

        super().pre_print_tasks()

        # skip auto focus if test
        if check_version(self.print_settings) == "v999":
            return

        try:
            # Step 1: Get calibration positions from calibration position log
            self.calibration_positions = get_last_calibration_positions_from_logs()

            # Step 2: Perform measurements for each light engine
            for le in config_dict["light_engines"]:

                self.light_engine = le
                self.light_engine_alignment = self.light_engines[le].config_dict["orientation"]
                self.led_num = 0
                
                # a. move to measurement position
                self.move_xyf_stages(
                    0,
                    0,
                    0,
                    coord_system=f"fiber_{le}",
                    is_wintech=("wintech" in le),
                )
                time.sleep(1.0)

                # b. run photodiode algorithm to find best focus
                self.find_photodiode_position_and_focus(rough_pass=False)

                # c. calculate focus drift and move focus stage
                # target_focus = self.calibration_positions.get(
                #     f"{le}_focus_offset", 0
                # )

                photodiode_reading = round(
                    self.focus_stage.getFocusPosition() * 1000, 1
                )
                async_file_hander.write(
                    self.photodiode_focus_log,
                    f"{datetime.now().strftime(ts)},{le.capitalize()} Measured Position {photodiode_reading}\n",
                )
                focus_drift = 0 - photodiode_reading
                self.move_xyf_stages(
                    None,
                    None,
                    focus_drift,
                    coord_system=f"fiber_{le}",
                    is_wintech=("wintech" in le),
                )
                time.sleep(1.0)

                async_file_hander.write(
                    self.photodiode_focus_log,
                    f"{datetime.now().strftime(ts)},{le.capitalize()} Drift,{focus_drift}\n",
                )

                # d. update coordinate systems with new focus positions
                # self.coord_systems[f"fiber_{le}"]["Focus"] += (
                #     focus_drift / 1000
                # )
                # self.coord_systems[le]["Focus"] += focus_drift / 1000

                fiber_position = photodiode_reading
                coord_diff = (self.coord_systems[f"{le}"]["Focus"] - self.coord_systems[f"fiber_{le}"]["Focus"])*1000
                le_position = coord_diff + fiber_position

                last_positions = get_last_calibration_positions_from_logs()
                last_positions[f"{le}_focus_base"] = float(f"{le_position:.1f}")
                write_to_position_log(last_positions)
            
        except Exception as ex:
            log.critical("Error occured in photodiode focus measurement (%s)", ex, exc_info=True)
            self.failed_hardware["Keyence Measurement"] = None
            raise PrintingException()

    def move_xyf_stages(self, x_pos, y_pos, focus_pos, coord_system, is_wintech=False):
        _x_pos = x_pos / 1000 + self.coord_systems[coord_system]["X"] if x_pos is not None else None
        _y_pos = y_pos / 1000 + self.coord_systems[coord_system]["Y"] if y_pos is not None else None
        _focus_pos = focus_pos / 1000 + self.coord_systems[coord_system]["Focus"] if focus_pos is not None else None
        if is_wintech:
            _x_pos += (
                self.calibration_positions.get("x_drift", 0.0)
                + self.calibration_positions.get("xy_shift", 0.0) * _y_pos / 1000
                + self.calibration_positions.get("xx_shift", 0.0) * _x_pos / 1000
            ) / 1000 if x_pos is not None else None
            _y_pos += (
                self.calibration_positions.get("y_drift", 0.0)
                + self.calibration_positions.get("yx_shift", 0.0) * _x_pos / 1000
                + self.calibration_positions.get("yy_shift", 0.0) * _y_pos / 1000
            ) / 1000 if y_pos is not None else None

        self.focus_thread = self.focus_stage.threadedFocusMove(
            log, _focus_pos, join=False
        )
        time.sleep(0.05)
        self.xy_threads = self.xy_stage.threadedXYMove(log, _x_pos, _y_pos, join=False)
        

        # Wait for moves to complete
        for thread in self.xy_threads:
            if thread is not None:
                thread.join()
                if thread.exception is not None:
                    log.critical("Unable to move xy stage")
                    self.failed_hardware["XY Stage"] = self.xy_stage
                    raise PrintingException()
        if self.focus_thread is not None:
            self.focus_thread.join()
            if self.focus_thread.exception is not None:
                log.critical("Unable to move focus stage")
                self.failed_hardware["Focus Stage"] = self.focus_stage
                raise PrintingException()

    def find_photodiode_position_and_focus(self, position="center", rough_pass=True, log_file="xyz_test_data.csv", progress=(0,100)):
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
                rough_pass=rough_pass,
                log_file=log_file, 
                orders=["X", "Y", "X", "Y"], 
                step_sizes=[0.01, 0.01, 0.0025, 0.0025], 
                step_counts=[20, 20, 20, 20], 
                images=[["v_4px_edges.png"], ["v_4px_edges.png"], ["v_4px_edges.png"], ["v_4px_edges.png"]], 
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

    def _find_photodiode_position(self, rough_pass=True, log_file="photodiode_focus.csv", orders=[], step_sizes=[], step_counts=[], images=[], use_find_peaks=[], use_fits=[], adjust_coords=[], use_positions=[], progress=(0,100)):
        self.test_log = str(self.current_job / "logs" / log_file)

        xy_threads = None
        focus_thread = None
        screen_thread = None

        step = 0
        self._update_progress(step, sum(step_counts), progress)

        x_pos = self.xy_stage.getXYPosition(axis='X')
        y_pos = self.xy_stage.getXYPosition(axis='Y')
        z_pos = self.focus_stage.getFocusPosition()
        
        self.light_engines[self.light_engine].setup_exposure(1000, led_power=100, repeat=0, is_grayscale_corrected=False, led_num=self.led_num)
        self.light_engines[self.light_engine].perform_exposure()

        for stage, step_size, step_count, image, _use_find_peaks, use_fit, adjust_coord, use_position in zip(orders, step_sizes, step_counts, images, use_find_peaks, use_fits, adjust_coords, use_positions):
            if step_size >= 0.1 and not rough_pass:
                continue
            
            if self.printing_stopped.is_set():
                return
            
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
                        self.coord_systems["fiber_visitech"][stage] = z_pos
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

    def get_exposure_defocus(self, settings, light_engine):
        screen_light_engine = self.convert_le_to_screen_le(light_engine)
        last_positions = get_last_calibration_positions_from_logs()
        self.focus = (last_positions.get(f"{screen_light_engine}_focus_base",0) + last_positions.get(f"{screen_light_engine}_focus_offset",0))/1000

        self.previous_defocus = self.defocus_um
        self.defocus_um = settings["Relative focus position (um)"]
            
    def post_print_tasks(self):
        self.focus = self.coord_systems["parked"]["Focus"]
        super().post_print_tasks()

