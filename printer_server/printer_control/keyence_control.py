import time
import logging
from datetime import datetime

import printer_server.views.home as home
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.printer_control.print_control import PrintControl, PrintingException, run_in_thread
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles
from printer_server.views.calibration import (
    get_last_calibration_positions_from_logs,
)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class KeyenceControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.keyence = driver_handles.keyence
        self.calibration_positions = None
        self.keyence_offset_targets = None
        self.last_exposure_le = None

        self.default_position_settings = None
        self.default_x_offset = None
        self.default_y_offset = None
        self.default_light_engine = None
        self.wintech_thermal_drift_measurements = {}
        self.wintech_thermal_drift = 0
        self.x_offset = None
        self.y_offset = None

        self.thermal_drift_log = str(self.current_job / "logs" / "thermal_drift_data.csv")

    def connect_hardware(self):
        keyence_thread = Thread(log, name="keyence_control_connect_thread", target=self.keyence.connect)
        keyence_thread.start()
        super().connect_hardware()
        keyence_thread.join()
        if not self.keyence.connected or keyence_thread.exception is not None:
            log.error("Keyence failed to connect!")
            self.failed_hardware["Keyence Sensor"] = self.keyence

    def update_measurement_progress(self):
        msg = {
            "percent": int(100 * self.measurement_index / self.measurement_count),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "text": f"Measurement {self.measurement_index+1}/{self.measurement_count}",
        }
        home.update_printer_state("print progress", msg)
        self.measurement_index += 1

    def create_logs(self):
        super().create_logs()

        async_file_hander.write(
            self.thermal_drift_log,
            "time,thermal_drift\n",
        )

    def pre_print_tasks(self):
        """
        Step-by-step procedure for pre-print keyence sensor calibration:
        
        1. Get calibration positions from calibration position log
        # 2. Move focus stage to each light engine position to improve repeatability
        2. Get default settings from print configuration
        3. Initialize measurement tracking variables
        4. Build list of measurement positions
        5. Move build platform up for measurements
        6. Perform measurements for each light engine:
            a. Get keyence target position
            b. Move to origin measurement position (0,0 or default x/y)
            c. Get several readings and adjusting focus between
            d. Get final reading and calculate drift from initial target
            e. Update coordinate systems with new focus positions
            f. Get measurements at each unique x,y offset position:
                - Move to offset position
                - Get keyence reading
                - Calculate and store focus offset
            g. Repeat f but for wintech instead of keyence_wintech
        7. Move build platform back down
        """
        super().pre_print_tasks()

        try:
            # Step 1: Get calibration positions from calibration position log
            self.calibration_positions = get_last_calibration_positions_from_logs()

            # # Step 2: Move focus stage to each light engine position to improve repeatability
            # for light_engine in config_dict["light_engines"]:
            #     self.focus_stage.threadedFocusMove(log, self.coord_systems[f"keyence_{light_engine}"]["Focus"])
            #     time.sleep(1.0)

            # Step 2: Get default settings from print configuration
            try:
                defaults_layer_settings = self.print_settings.get("Default layer settings")
                default_image_settings = defaults_layer_settings.get("Image settings")
                self.default_position_settings = defaults_layer_settings.get("Position settings")
            except:
                # needed for json 999
                return
            self.default_x_offset = default_image_settings.get("Image x offset (um)", 0)
            self.default_y_offset = default_image_settings.get("Image y offset (um)", 0)
            self.default_light_engine = default_image_settings.get(
                "Light engine", config_dict["light_engines"][0]
            )

            # Step 3: Initialize measurement tracking variables
            self.keyence_offset_targets = {}
            self.measurement_index = 0
            self.measurement_count = 0
            repeats = 3

            # Step 4: Build list of measurement positions
            for light_engine in config_dict["light_engines"]:
                self.measurement_count += repeats + 2
                self.keyence_offset_targets[f"keyence_{light_engine}"] = {}
                if light_engine == "wintech":
                    self.keyence_offset_targets[light_engine] = {}
                for i, layer in enumerate(self.layer_map):
                    image_settings_list = self.get_image_settings(self.print_settings["Layers"][layer[0]])
                    for j, settings in enumerate(image_settings_list):
                        x_offset = float(settings.get("Image x offset (um)", self.default_x_offset))
                        y_offset = float(settings.get("Image y offset (um)", self.default_y_offset))
                        layer_light_engine = settings.get(
                            "Light engine", self.default_light_engine
                        )
                        if (layer_light_engine == light_engine) or (
                            light_engine in layer_light_engine
                        ):
                            if (
                                f"{x_offset}, {y_offset}"
                                not in self.keyence_offset_targets[f"keyence_{light_engine}"]
                            ):
                                self.keyence_offset_targets[f"keyence_{light_engine}"][f"{x_offset}, {y_offset}"] = None
                                self.measurement_count += 1
                            if light_engine == "wintech" and (
                                f"{x_offset}, {y_offset}"
                                not in self.keyence_offset_targets[light_engine]
                            ):
                                self.keyence_offset_targets[light_engine][f"{x_offset}, {y_offset}"] = None
                                self.measurement_count += 1

            # Step 5: Move build platform up for measurements
            self.move_build_platform_up(self.default_position_settings)

            # Step 6: Perform measurements for each light engine
            for light_engine in config_dict["light_engines"]:
                self.update_measurement_progress()

                # Step 6a: Get keyence target position
                target_position = self.calibration_positions.get(f"keyence_{light_engine}",0)
                self.write_to_event_log(
                    f"{light_engine.capitalize()} Keyence Target Position: {target_position}"
                )

                # Step 6b: Move to origin measurement position (0,0 or default x/y)
                x_pos = self.default_x_offset/1000 + self.coord_systems[f"keyence_{light_engine}"]["X"]
                y_pos = self.default_y_offset/1000 + self.coord_systems[f"keyence_{light_engine}"]["Y"]
                if "wintech" in light_engine:
                    x_pos += (self.calibration_positions.get("x_drift",0.0) + self.calibration_positions.get("xy_shift",0.0)*self.default_y_offset/1000 + self.calibration_positions.get("xx_shift",0.0)*self.default_x_offset/1000)/1000
                    y_pos += (self.calibration_positions.get("y_drift",0.0) + self.calibration_positions.get("yx_shift",0.0)*self.default_x_offset/1000 + self.calibration_positions.get("yy_shift",0.0)*self.default_y_offset/1000)/1000

                focus_pos = self.coord_systems[f"keyence_{light_engine}"]["Focus"]
                self.xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False)
                self.focus_thread = self.focus_stage.threadedFocusMove(log, focus_pos, join=False)
                
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
                time.sleep(1.0)

                # Step 6c: Get several readings and adjusting focus between
                focus_drift = 0
                for i in range(repeats):
                    keyence_reading = self.keyence.read_sensor(light_engine)
                    self.write_to_event_log(
                        f"{light_engine.capitalize()} Keyence Measured Position {i}: {keyence_reading}"
                    )
                    self.update_measurement_progress()
                    focus_drift += target_position - keyence_reading
                    self.focus_stage.threadedFocusMove(log, self.coord_systems[f"keyence_{light_engine}"]["Focus"] + focus_drift/1000)
                    time.sleep(1.0)

                # Step 6d: Get final reading and calculate drift from target
                keyence_error = self.keyence.read_sensor(light_engine)
                self.write_to_event_log(
                    f"{light_engine.capitalize()} Keyence Error: {target_position - keyence_error}"
                )
                
                self.write_to_event_log(
                    f"{light_engine.capitalize()} Keyence Drift: {focus_drift}"
                )

                # Step 6e: Update coordinate systems with new focus positions
                self.coord_systems[f"keyence_{light_engine}"]["Focus"] += focus_drift/1000
                self.coord_systems[light_engine]["Focus"] += focus_drift/1000

                # Step 6f: Get measurements at each unique x,y offset position
                for measurement in list(self.keyence_offset_targets[f"keyence_{light_engine}"]):
                    measurement = measurement.split(", ")
                    x_offset = float(measurement[0])
                    y_offset = float(measurement[1])

                    self.update_measurement_progress()
                    # Move to offset position
                    x_pos = x_offset/1000 + self.coord_systems[f"keyence_{light_engine}"]["X"]
                    y_pos = y_offset/1000 + self.coord_systems[f"keyence_{light_engine}"]["Y"]
                    if "wintech" in light_engine:
                        x_pos += (self.calibration_positions.get("x_drift",0.0) + self.calibration_positions.get("xy_shift",0.0)*y_offset/1000 + self.calibration_positions.get("xx_shift",0.0)*x_offset/1000)/1000
                        y_pos += (self.calibration_positions.get("y_drift",0.0) + self.calibration_positions.get("yx_shift",0.0)*x_offset/1000 + self.calibration_positions.get("yy_shift",0.0)*y_offset/1000)/1000
                    self.xy_stage.threadedXYMove(log, x_pos, y_pos)
                    time.sleep(1.0)

                    # Get keyence reading
                    keyence_reading = self.keyence.read_sensor(light_engine)

                    # Calculate and store focus offset
                    self.keyence_offset_targets[f"keyence_{light_engine}"][f"{x_offset}, {y_offset}"] = keyence_reading

                # Step 6g: Repeat f but for wintech instead of keyence_wintech
                if light_engine == "wintech":
                    self.focus_stage.threadedFocusMove(log, self.coord_systems[light_engine]["Focus"])
                    time.sleep(1.0)
                    for measurement in list(self.keyence_offset_targets[light_engine]):
                        measurement = measurement.split(", ")
                        x_offset = float(measurement[0])
                        y_offset = float(measurement[1])

                        self.update_measurement_progress()
                        # Move to offset position
                        x_pos = x_offset/1000 + self.coord_systems[f"{light_engine}"]["X"]
                        y_pos = y_offset/1000 + self.coord_systems[f"{light_engine}"]["Y"]
                        x_pos += (self.calibration_positions.get("x_drift",0.0) + self.calibration_positions.get("xy_shift",0.0)*y_offset/1000 + self.calibration_positions.get("xx_shift",0.0)*x_offset/1000)/1000
                        y_pos += (self.calibration_positions.get("y_drift",0.0) + self.calibration_positions.get("yx_shift",0.0)*x_offset/1000 + self.calibration_positions.get("yy_shift",0.0)*y_offset/1000)/1000
                        self.xy_stage.threadedXYMove(log, x_pos, y_pos)
                        time.sleep(1.0)

                        # Get keyence reading
                        keyence_reading = self.keyence.read_sensor(light_engine)

                        # Calculate and store focus offset
                        self.keyence_offset_targets[light_engine][f"{x_offset}, {y_offset}"] = keyence_reading

            self.update_measurement_progress()
            self.write_to_event_log(f"Keyence Focus Offsets: {self.keyence_offset_targets}")

            # Step 7: Move build platform down
            self.move_build_platform_down(self.default_position_settings)

        except Exception as ex:
            log.critical("Error occured in keyence measurement (%s)", ex, exc_info=True)
            self.failed_hardware["Keyence Measurement"] = None
            raise PrintingException()

    def pre_exposure_tasks(self, settings, light_engine):
        self.x_offset = float(settings.get("Image x offset (um)", self.default_x_offset))
        self.y_offset = float(settings.get("Image y offset (um)", self.default_y_offset))

        if light_engine == "wintech" and self.last_exposure_le != "wintech":
            # Move to origin measurement position (0,0 or default x/y)
            x_pos = self.default_x_offset/1000 + self.coord_systems[f"keyence_{light_engine}"]["X"]
            y_pos = self.default_y_offset/1000 + self.coord_systems[f"keyence_{light_engine}"]["Y"]
            if "wintech" in light_engine:
                x_pos += (self.calibration_positions.get("x_drift",0.0) + self.calibration_positions.get("xy_shift",0.0)*self.default_y_offset/1000 + self.calibration_positions.get("xx_shift",0.0)*self.default_x_offset/1000)/1000
                y_pos += (self.calibration_positions.get("y_drift",0.0) + self.calibration_positions.get("yx_shift",0.0)*self.default_x_offset/1000 + self.calibration_positions.get("yy_shift",0.0)*self.default_y_offset/1000)/1000

            focus_pos = self.coord_systems[f"keyence_{light_engine}"]["Focus"]
            self.xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False)
            self.focus_thread = self.focus_stage.threadedFocusMove(log, focus_pos, join=False)
            
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
            time.sleep(1.0)

            # Measure and set thermal drift
            origin_target = self.calibration_positions.get(f"keyence_{light_engine}",0)
            self.write_to_event_log(f"Origin target offset: {origin_target}")
            keyence_reading = self.keyence.read_sensor(light_engine)
            self.write_to_event_log(f"Origin sensor reading: {keyence_reading}")
            self.wintech_thermal_drift = origin_target - keyence_reading
            self.write_to_event_log(f"Origin thermal drift: {self.wintech_thermal_drift}")

            ts = "%Y-%m-%d %H:%M:%S.%f"
            async_file_hander.write(
                self.thermal_drift_log,
                f"{datetime.now().strftime(ts)},{self.wintech_thermal_drift}\n"
            )

        return super().pre_exposure_tasks(settings, light_engine)
            
    def post_exposure_tasks(self, light_engine, msg):
        """
        Read the keyence sensor after exposure then compare it to the starting values.
        This lets us measure changing wintech focus over the course of
        the print without needing to constantly return the wintech to the center.
        """
        if light_engine == "wintech":
            keyence_reading = self.keyence.read_sensor(light_engine)
            if keyence_reading != -9999.99:
                # calculate thermal drift
                target_position = self.keyence_offset_targets[light_engine][f"{self.x_offset}, {self.y_offset}"]
                self.write_to_event_log(f"Offset Target: {target_position}")
                self.write_to_event_log(f"Sensor reading: {keyence_reading}")
                self.write_to_event_log(f"Defocus: {self.defocus_um}")
                self.write_to_event_log(f"Thermal drift: {target_position + self.defocus_um - keyence_reading}")
                self.wintech_thermal_drift_measurements[f"{self.x_offset}, {self.y_offset}"] = target_position + self.defocus_um - keyence_reading
        self.last_exposure_le = light_engine
        super().post_exposure_tasks(light_engine, msg)

    def move_build_platform(self, position_settings, layer):
        """
        Calculate new thermal drift averages using keyence measurements taken during layer's exposures.
        """

        if len(self.wintech_thermal_drift_measurements.values()) > 0:
            self.wintech_thermal_drift = sum(self.wintech_thermal_drift_measurements.values())/len(self.wintech_thermal_drift_measurements.values())
            self.wintech_thermal_drift_measurements = {}
            self.write_to_event_log(
                f"Wintech Thermal Drift Offsets: {list(self.wintech_thermal_drift_measurements.values())}"
            )
            self.write_to_event_log(
                f"Average Keyence Thermal Drift: {self.wintech_thermal_drift}"
            )
            ts = "%Y-%m-%d %H:%M:%S.%f"
            async_file_hander.write(
                self.thermal_drift_log,
                f"{datetime.now().strftime(ts)},{self.wintech_thermal_drift}\n"
            )
        super().move_build_platform(position_settings, layer)


    def get_exposure_defocus(self, settings, light_engine):
        screen_light_engine = self.convert_le_to_screen_le(light_engine)
        self.focus = self.coord_systems[screen_light_engine]["Focus"]

        defocus_um = settings["Relative focus position (um)"]

        # keyence correction
        origin_target = self.calibration_positions.get(f"keyence_{light_engine}",0)
        keyence_measurement = origin_target - self.keyence_offset_targets[f"keyence_{screen_light_engine}"][
            f"{self.x_offset}, {self.y_offset}"
        ]

        self.defocus_um = (defocus_um + keyence_measurement)
        if light_engine == "wintech":
            self.defocus_um += self.wintech_thermal_drift

    def post_print_tasks(self):
        self.focus = self.coord_systems["parked"]["Focus"]
        super().post_print_tasks()