import time
import logging
from datetime import datetime

import printer_server.views.home as home
from printer_server.threading_wrapper import Thread
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
        self.keyence_measurement_list = None

        self.default_position_settings = None
        self.default_x_offset = None
        self.default_y_offset = None
        self.default_light_engine = None

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

    def pre_print_tasks(self):
        super().pre_print_tasks()

        try:
            calibration_positions = get_last_calibration_positions_from_logs()

            # Move focus around a little bit before print. Seems to help repeatablility
            for light_engine in config_dict["light_engines"]:
                self.focus_stage.threadedFocusMove(log, self.coord_systems[f"keyence_{light_engine}"]["Focus"])
                time.sleep(1.0)

            """Move keyence sensor to all exposure positions and get focus offsets"""
            defaults_layer_settings = self.print_settings.get("Default layer settings")
            default_image_settings = defaults_layer_settings.get("Image settings")
            self.default_position_settings = defaults_layer_settings.get("Position settings")
            self.default_x_offset = default_image_settings.get("Image x offset (um)", 0)
            self.default_y_offset = default_image_settings.get("Image y offset (um)", 0)
            self.default_light_engine = default_image_settings.get(
                "Light engine", config_dict["light_engines"][0]
            )

            self.keyence_measurement_list = {}

            # List all exposure positions
            self.measurement_index = 0
            self.measurement_count = 0
            for light_engine in config_dict["light_engines"]:
                self.measurement_count += 2
                self.keyence_measurement_list[light_engine] = {}
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
                                not in self.keyence_measurement_list[light_engine]
                            ):
                                self.keyence_measurement_list[light_engine][f"{x_offset}, {y_offset}"] = None
                                self.measurement_count += 1

            self.move_build_platform_up(self.default_position_settings)
            time.sleep(1.0)

            for light_engine in config_dict["light_engines"]:
                self.update_measurement_progress()

                # load keyence focal position
                start_position = calibration_positions.get(f"keyence_{light_engine}",0)
                self.write_to_event_log(
                    f"{light_engine.capitalize()} Keyence Target Position: {start_position}"
                )
                # goto position
                x_pos = self.default_x_offset/1000 + self.coord_systems[f"keyence_{light_engine}"]["X"]
                y_pos = self.default_y_offset/1000 + self.coord_systems[f"keyence_{light_engine}"]["Y"]
                if "wintech" in light_engine:
                    x_pos += (calibration_positions.get("x_drift",0.0) + calibration_positions.get("xy_shift",0.0)*self.default_y_offset/1000 + calibration_positions.get("xx_shift",0.0)*self.default_x_offset/1000)/1000
                    y_pos += (calibration_positions.get("y_drift",0.0) + calibration_positions.get("yx_shift",0.0)*self.default_x_offset/1000 + calibration_positions.get("yy_shift",0.0)*self.default_y_offset/1000)/1000

                focus_pos = self.coord_systems[f"keyence_{light_engine}"]["Focus"]
                self.xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False)
                self.focus_thread = self.focus_stage.threadedFocusMove(log, focus_pos, join=False)
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
                time.sleep(5.0)

                # get keyence reading
                temp_position = self.keyence.read_sensor(light_engine)

                self.update_measurement_progress()

                focus_pos = self.coord_systems[f"keyence_{light_engine}"]["Focus"] + (start_position - temp_position)/1000
                self.focus_stage.threadedFocusMove(log, focus_pos)
                time.sleep(1.0)

                temp_position = self.keyence.read_sensor(light_engine)
                current_position = (
                    self.focus_stage.getFocusPosition()
                )
                focus_drift = (
                    self.coord_systems[f"keyence_{light_engine}"]["Focus"] * 1000 - current_position * 1000
                )
                self.write_to_event_log(
                    f"{light_engine.capitalize()} Keyence Measured Position: {temp_position}"
                )
                self.write_to_event_log(
                    f"{light_engine.capitalize()} Keyence Drift: {focus_drift}"
                )

                self.coord_systems[f"keyence_{light_engine}"]["Focus"] = current_position
                self.coord_systems[light_engine]["Focus"] = (
                    self.coord_systems[light_engine]["Focus"] - focus_drift/1000
                )

                # get keyence offsets
                for measurement in list(self.keyence_measurement_list[light_engine]):
                    measurement = measurement.split(", ")
                    x_offset = float(measurement[0])
                    y_offset = float(measurement[1])

                    self.update_measurement_progress()

                    x_pos = x_offset/1000 + self.coord_systems[f"keyence_{light_engine}"]["X"]
                    y_pos = y_offset/1000 + self.coord_systems[f"keyence_{light_engine}"]["Y"]
                    if "wintech" in light_engine:
                        x_pos += (calibration_positions.get("x_drift",0.0) + calibration_positions.get("xy_shift",0.0)*y_offset/1000 + calibration_positions.get("xx_shift",0.0)*x_offset/1000)/1000
                        y_pos += (calibration_positions.get("y_drift",0.0) + calibration_positions.get("yx_shift",0.0)*x_offset/1000 + calibration_positions.get("yy_shift",0.0)*y_offset/1000)/1000
                    self.xy_stage.threadedXYMove(log, x_pos, y_pos)
                    time.sleep(5.0)

                    keyence_position = self.keyence.read_sensor(light_engine)
                    self.keyence_measurement_list[light_engine][
                        f"{x_offset}, {y_offset}"
                    ] = (start_position - keyence_position)

            self.update_measurement_progress()
            self.write_to_event_log(f"Keyence Focus Offsets: {self.keyence_measurement_list}")
            self.move_build_platform_down(self.default_position_settings)
        except Exception as ex:
            log.critical("Error occured in keyence measurement (%s)", ex, exc_info=True)
            self.failed_hardware["Keyence Measurement"] = None
            raise PrintingException()

    def get_exposure_defocus(self, settings, light_engine):
        screen_light_engine = self.convert_le_to_screen_le(light_engine)
        self.focus = self.coord_systems[screen_light_engine]["Focus"]

        defocus_um = settings["Relative focus position (um)"]
        x_offset = float(settings.get("Image x offset (um)", self.default_x_offset))
        y_offset = float(settings.get("Image y offset (um)", self.default_y_offset))

        # keyence correction
        keyence_measurement = self.keyence_measurement_list[screen_light_engine][
            f"{x_offset}, {y_offset}"
        ]

        self.defocus_um = (defocus_um + keyence_measurement)

    def post_print_tasks(self):
        self.focus = self.coord_systems["parked"]["Focus"]
        super().post_print_tasks()