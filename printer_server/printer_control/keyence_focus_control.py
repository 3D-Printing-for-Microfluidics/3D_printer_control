import time
import math
import logging
from datetime import datetime

import printer_server.views.home as home
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.print_file_validator import check_version
from printer_server.printer_control.print_control import (
    PrintControl,
    PrintingException,
    run_in_thread,
)
from printer_server.hardware_configuration.hardware_configuration import (
    config_dict,
    driver_handles,
)
from printer_server.views.calibration import (
    get_last_calibration_positions_from_logs, write_to_position_log
)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
ts = "%Y-%m-%d %H:%M:%S.%f"


class KeyenceFocusControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.keyence = driver_handles.keyence
        self.direct_focal_measurement = None
        self.thermal_drift_measurement = None
        self.calibration_positions = None
        self.keyence_offset_targets = None
        self.last_exposure_le = None
        self.need_origin_keyence_measurement = False
        self.wintech_thermal_drift_readings = {}
        self.failed_thermal_drift_readings = 0
        self.wintech_thermal_drift = 0

        self.default_position_settings = None
        self.default_x_offset = None
        self.default_y_offset = None
        self.default_light_engine = None
        self.x_offset = None
        self.y_offset = None

        self.keyence_focus_log = str(self.current_job / "logs" / "keyence_focus_data.csv")

    def connect_hardware(self):
        keyence_thread = Thread(
            log, name="keyence_focus_control_connect_thread", target=self.keyence.connect
        )
        keyence_thread.start()
        super().connect_hardware()
        keyence_thread.join()
        if not self.keyence.connected or keyence_thread.exception is not None:
            log.error("Keyence failed to connect!")
            self.failed_hardware["Keyence Sensor"] = self.keyence

        self.direct_focal_measurement = config_dict["keyence"].get("direct_focal_measurement", False)
        self.thermal_drift_measurement = config_dict["keyence"].get("thermal_drift_measurement", {"wintech": False, "visitech": False})

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
            self.keyence_focus_log,
            "time,data_type,data\n",
        )

    def pre_print_tasks(self):
        """
        Step-by-step procedure for pre-print keyence sensor calibration:

        1. Get calibration positions from calibration position log
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

        # skip auto focus if test
        if check_version(self.print_settings) == "v999":
            return

        try:
            # Step 1: Get calibration positions from calibration position log
            self.calibration_positions = get_last_calibration_positions_from_logs()

            # Step 2: Get default settings from print configuration
            defaults_layer_settings = self.print_settings.get(
                "Default layer settings"
            )
            default_image_settings = defaults_layer_settings.get("Image settings")
            self.default_position_settings = defaults_layer_settings.get(
                "Position settings"
            )
            self.default_x_offset = default_image_settings.get("Image x offset (um)", 0)
            self.default_y_offset = default_image_settings.get("Image y offset (um)", 0)
            self.default_light_engine = default_image_settings.get(
                "Light engine", config_dict["light_engines"][0]
            )

            # Step 3: Initialize measurement tracking variables
            self.keyence_offset_targets = {}
            self.measurement_index = 0
            self.measurement_count = 0

            # Step 4: Build list of measurement positions
            if self.direct_focal_measurement:
                for light_engine in config_dict["light_engines"]:
                    self.measurement_count += 3
                    self.keyence_offset_targets[f"active_{light_engine}"] = {}
                    if self.thermal_drift_measurement.get(light_engine, False):
                        self.keyence_offset_targets[light_engine] = {}
                    for i, layer in enumerate(self.layer_map):
                        image_settings_list = self.get_image_settings(
                            self.print_settings["Layers"][layer[0]]
                        )
                        for j, settings in enumerate(image_settings_list):
                            x_offset = float(
                                settings.get("Image x offset (um)", self.default_x_offset)
                            )
                            y_offset = float(
                                settings.get("Image y offset (um)", self.default_y_offset)
                            )
                            layer_light_engine = settings.get(
                                "Light engine", self.default_light_engine
                            )
                            if (layer_light_engine == light_engine) or (
                                light_engine in layer_light_engine
                            ):
                                if (
                                    f"{x_offset}, {y_offset}"
                                    not in self.keyence_offset_targets[
                                        f"active_{light_engine}"
                                    ]
                                ):
                                    self.keyence_offset_targets[f"active_{light_engine}"][
                                        f"{x_offset}, {y_offset}"
                                    ] = None
                                    self.measurement_count += 1
                                if self.thermal_drift_measurement.get(light_engine, False) and (
                                    f"{x_offset}, {y_offset}"
                                    not in self.keyence_offset_targets[light_engine]
                                ):
                                    self.keyence_offset_targets[light_engine][
                                        f"{x_offset}, {y_offset}"
                                    ] = None
                                    self.measurement_count += 1

            if self.direct_focal_measurement:
                # Step 5: Move build platform up for measurements
                self.move_build_platform_up(self.default_position_settings)

            # Step 6: Perform measurements for each light engine
            for light_engine in config_dict["light_engines"]:
                self.update_measurement_progress()

                # Step 6a: Get keyence target position
                # target_position = self.calibration_positions.get(
                #     f"active_{light_engine}_focus", 0
                # )
                # log.debug("Keyence target position for %s: %s", light_engine, target_position)
                # target_tip = self.calibration_positions.get(
                #     f"active_{light_engine}_tip", 0
                # )
                # log.debug("Keyence target tip for %s: %s", light_engine, target_tip)
                # target_tilt = self.calibration_positions.get(
                #     f"active_{light_engine}_tilt", 0
                # )
                # log.debug("Keyence target tilt for %s: %s", light_engine, target_tilt)

                # async_file_hander.write(
                #     self.keyence_focus_log,
                #     f"{datetime.now().strftime(ts)},{light_engine.capitalize()} Target Position,{target_position},{light_engine.capitalize()} Target Tip,{target_tip},{light_engine.capitalize()} Target Tilt,{target_tilt}\n",
                # )
                # async_file_hander.write(
                #     self.keyence_focus_log,
                #     f"{datetime.now().strftime(ts)},{light_engine.capitalize()} Target Position,{target_position}\n",
                # )

                # Step 6b: Move to origin measurement position (0,0 or default x/y)
                self.move_xyf_stages(
                    self.default_x_offset,
                    self.default_y_offset,
                    0,
                    coord_system=f"keyence_{light_engine}",
                    is_wintech=("wintech" in light_engine),
                )
                log.debug("Default x offset: %s, default y offset: %s",
                          self.default_x_offset, self.default_y_offset)
                time.sleep(1.0)

                # Step 6c: Get keyence reading
                keyence_reading = self.keyence.read_sensor(light_engine)
                async_file_hander.write(
                    self.keyence_focus_log,
                    f"{datetime.now().strftime(ts)},{light_engine.capitalize()} Measured Position {i},{keyence_reading}\n",
                )
                self.update_measurement_progress()
                focus_drift = - keyence_reading
                self.move_xyf_stages(
                    None,
                    None,
                    focus_drift,
                    coord_system=f"keyence_{light_engine}",
                    is_wintech=("wintech" in light_engine),
                )
                time.sleep(1.0)

                # Step 6d: Get final reading and calculate drift from target
                keyence_error = self.keyence.read_sensor(light_engine)
                async_file_hander.write(
                    self.keyence_focus_log,
                    f"{datetime.now().strftime(ts)},{light_engine.capitalize()} Error,{0 - keyence_error}\n",
                )
                async_file_hander.write(
                    self.keyence_focus_log,
                    f"{datetime.now().strftime(ts)},{light_engine.capitalize()} Drift,{focus_drift}\n",
                )

                # Step 6e: Update coordinate systems with new focus positions
                # self.coord_systems[f"keyence_{light_engine}"]["Focus"] += (
                #     focus_drift / 1000
                # )
                # self.coord_systems[light_engine]["Focus"] += focus_drift / 1000

                keyence_position = self.coord_systems[f"keyence_{light_engine}"]["Focus"]*1000 + focus_drift
                coord_diff = (self.coord_systems[f"{light_engine}"]["Focus"] - self.coord_systems[f"keyence_{light_engine}"]["Focus"])*1000
                le_position = coord_diff + keyence_position

                last_positions = get_last_calibration_positions_from_logs()
                last_positions[f"_{light_engine}_focus"] = float(f"{le_position:.1f}")
                write_to_position_log(last_positions)

                # Step 6f: Get measurements at each unique x,y offset position
                if self.direct_focal_measurement:
                    for measurement in list(
                        self.keyence_offset_targets[f"active_{light_engine}"]
                    ):
                        measurement = measurement.split(", ")
                        x_offset = float(measurement[0])
                        y_offset = float(measurement[1])

                        self.update_measurement_progress()
                        self.move_xyf_stages(
                            x_offset,
                            y_offset,
                            None,
                            coord_system=f"keyence_{light_engine}",
                            is_wintech=("wintech" in light_engine),
                        )
                        time.sleep(1.0)

                        # Get keyence reading
                        keyence_reading = self.keyence.read_sensor(light_engine)

                        # Calculate and store focus offset
                        self.keyence_offset_targets[f"active_{light_engine}"][
                            f"{x_offset}, {y_offset}"
                        ] = keyence_reading

                    if self.thermal_drift_measurement.get(light_engine, False):
                        # Step 6g: Repeat f but for wintech instead of keyence_wintech
                        self.move_xyf_stages(
                            None,
                            None,
                            0,
                            coord_system=light_engine,
                            is_wintech=("wintech" in light_engine),
                        )
                        time.sleep(1.0)
                        for measurement in list(self.keyence_offset_targets[light_engine]):
                            measurement = measurement.split(", ")
                            x_offset = float(measurement[0])
                            y_offset = float(measurement[1])

                            self.update_measurement_progress()
                            # Move to offset position
                            self.move_xyf_stages(
                                x_offset,
                                y_offset,
                                None,
                                coord_system=light_engine,
                                is_wintech=("wintech" in light_engine),
                            )
                            time.sleep(1.0)

                            # Get keyence reading
                            keyence_reading = self.keyence.read_sensor(light_engine)

                            # Calculate and store focus offset
                            self.keyence_offset_targets[light_engine][
                                f"{x_offset}, {y_offset}"
                            ] = keyence_reading

            self.update_measurement_progress()
            async_file_hander.write(
                self.keyence_focus_log,
                "\ntime,data_type,x,y,data\n",
            )
            if self.direct_focal_measurement:
                for k1, v1 in self.keyence_offset_targets.items():
                    for k2, v2 in v1.items():
                        async_file_hander.write(
                            self.keyence_focus_log,
                            f"{datetime.now().strftime(ts)},{k1} Offset Target Position,{k2},{v2}\n",
                        )
            async_file_hander.write(
                self.keyence_focus_log,
                "\ntime,data_type,data\n",
            )

            if self.direct_focal_measurement:
                # Move build platform down
                self.move_build_platform_down(self.default_position_settings)

        except Exception as ex:
            log.critical("Error occured in keyence focus measurement (%s)", ex, exc_info=True)
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

    def pre_exposure_tasks(self, settings, light_engine):
        """
        Setup for post exposure task, also after each non-wintech exposure,
        remeasure the thermal drift at keyence wintech origin
        """

        self.x_offset = float(settings.get("Image x offset (um)", self.default_x_offset))
        self.y_offset = float(settings.get("Image y offset (um)", self.default_y_offset))

        if self.thermal_drift_measurement.get(light_engine, False) and light_engine != self.last_exposure_le:
            if self.need_origin_keyence_measurement or (
                self.failed_thermal_drift_readings > 0
                and len(self.wintech_thermal_drift_readings.values()) == 0
            ):
                self.need_origin_keyence_measurement = False
                self.failed_thermal_drift_readings = 0

                self.move_xyf_stages(
                    self.default_x_offset,
                    self.default_y_offset,
                    0,
                    coord_system=f"keyence_{light_engine}",
                    is_wintech=("wintech" in light_engine),
                )
                time.sleep(1.0)

                # Measure and set thermal drift
                origin_target = self.calibration_positions.get(
                    f"active_{light_engine}_focus", 0
                )
                keyence_reading = self.keyence.read_sensor(light_engine)
                self.wintech_thermal_drift = origin_target - keyence_reading

                async_file_hander.write(
                    self.keyence_focus_log,
                    f"{datetime.now().strftime(ts)},Wintech Thermal Drift,{self.wintech_thermal_drift}\n",
                )

        return super().pre_exposure_tasks(settings, light_engine)

    def post_exposure_tasks(self, light_engine, msg):
        """
        Read the keyence sensor after exposure then compare it to the starting values.
        This lets us measure changing wintech focus (thermal drift) over the course of
        the print without needing to constantly return the wintech to the center.
        """
        if self.thermal_drift_measurement.get(light_engine, False):
            keyence_reading = self.keyence.read_sensor(light_engine)
            if keyence_reading != -9999.99:
                # calculate thermal drift
                target_position = self.keyence_offset_targets[light_engine][
                    f"{self.x_offset}, {self.y_offset}"
                ]
                self.wintech_thermal_drift_readings[
                    f"{self.x_offset}, {self.y_offset}"
                ] = (target_position + self.defocus_um - keyence_reading)
            else:
                self.failed_thermal_drift_readings += 1
        self.last_exposure_le = light_engine
        super().post_exposure_tasks(light_engine, msg)

    def move_build_platform(self, position_settings, layer):
        """
        Calculate new thermal drift averages using keyence measurements taken during layer's exposures.
        Reset dictionary for next layer
        """

        if len(self.wintech_thermal_drift_readings.values()) > 0:
            self.wintech_thermal_drift = sum(
                self.wintech_thermal_drift_readings.values()
            ) / len(self.wintech_thermal_drift_readings.values())
            self.wintech_thermal_drift_readings = {}
            async_file_hander.write(
                self.keyence_focus_log,
                f"{datetime.now().strftime(ts)},Wintech Thermal Drift,{self.wintech_thermal_drift}\n",
            )
        elif self.failed_thermal_drift_readings > 0:
            self.failed_thermal_drift_readings = 0
            self.need_origin_keyence_measurement = True
        super().move_build_platform(position_settings, layer)

    def get_exposure_defocus(self, settings, light_engine):
        screen_light_engine = self.convert_le_to_screen_le(light_engine)

        last_positions = get_last_calibration_positions_from_logs()
        self.focus = (last_positions.get(f"_{screen_light_engine}_focus",0) + last_positions.get(f"active_{screen_light_engine}_focus",0))/1000

        defocus_um = settings["Relative focus position (um)"]

        # keyence correction
        if self.direct_focal_measurement:
            keyence_measurement = (0 - self.keyence_offset_targets[f"active_{screen_light_engine}"][f"{self.x_offset}, {self.y_offset}"])
        else:
            keyence_measurement = 0

        self.previous_defocus = self.defocus_um
        self.defocus_um = defocus_um + keyence_measurement
        if self.thermal_drift_measurement.get(light_engine, False):
            self.defocus_um += self.wintech_thermal_drift

    def post_print_tasks(self):
        self.focus = self.coord_systems["parked"]["Focus"]
        super().post_print_tasks()
