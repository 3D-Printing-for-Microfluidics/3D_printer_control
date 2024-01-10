from printer_server.printer_control.print_control import *


def get_keyence_set_position(sensor):
    """Return the last focused position for the keyence sensor from the
    position log file.
    """
    return get_last_calibration_positions_from_logs()[f"keyence_{sensor}"]


class KeyenceControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.keyence = driver_handles.keyence
        self.keyence_measurement_list = None

    def connect_hardware(self):
        keyence_thread = Thread(log, name="keyence_control_setup_thread", target=self.keyence.connect, args=[])
        keyence_thread.start()
        super().connect_hardware()
        keyence_thread.join()
        if not self.keyence.connected:
            self.all_hardware_connected = False

    def initalize_hardware(self):
        super().initalize_hardware()

    def update_measurement_progress(self):
        msg = {
            "percent": int(100 * self.measurement_index / self.measurement_count),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "text": f"Measurement {self.measurement_index+1}/{self.measurement_count}",
        }
        home.update_printer_state("print progress", msg)
        self.measurement_index += 1

    def pre_print_tasks(self):
        """Move keyence sensor to all exposure positions and get focus offsets"""
        defaults_layer_settings = self.print_settings.get("Default layer settings")
        default_image_settings = defaults_layer_settings.get("Image settings")
        self.default_position_settings = defaults_layer_settings.get("Position settings")
        self.default_x_offset = default_image_settings.get("Image x offset (um)", 0)
        self.default_y_offset = default_image_settings.get("Image y offset (um)", 0)
        self.default_light_engine = default_image_settings.get(
            "Light engine", config_dict["screen"]["light_engines"][0]
        )

        keyence_indexes = config_dict["keyence"]["sensors"]
        self.keyence_measurement_list = {}

        # List all exposure positions
        self.measurement_index = 0
        self.measurement_count = 0
        for light_engine in config_dict["screen"]["light_engines"]:
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

        for light_engine in config_dict["screen"]["light_engines"]:
            self.update_measurement_progress()

            # load keyence focal position
            start_position = get_keyence_set_position(light_engine)
            self.write_to_event_log(
                f"{light_engine.capitalize()} Keyence Target Position: {start_position}"
            )
            # goto position
            move_all_galil(
                log,
                self.galil,
                self.default_x_offset + self.coord_systems["keyence"][light_engine]["X"],
                self.default_y_offset + self.coord_systems["keyence"][light_engine]["Y"],
                self.coord_systems["keyence"][light_engine]["Focus"],
                None,
            )
            time.sleep(5.0)
            # get keyence reading
            temp_position = float(
                self.keyence.read_all()[
                    keyence_indexes[light_engine]["measurement_index"] + 1
                ]
            )

            self.update_measurement_progress()

            move_all_galil(
                log,
                self.galil,
                None,
                None,
                self.coord_systems["keyence"][light_engine]["Focus"]
                + (start_position - temp_position),
                None,
            )
            time.sleep(1.0)
            temp_position = float(
                self.keyence.read_all()[
                    keyence_indexes[light_engine]["measurement_index"] + 1
                ]
            )
            current_position = (
                self.galil.cntsToMm(self.galil.getPosition(axis="Focus"), axis="Focus")
                * 1000
            )
            focus_drift = (
                self.coord_systems["keyence"][light_engine]["Focus"] - current_position
            )
            self.write_to_event_log(
                f"{light_engine.capitalize()} Keyence Measured Position: {temp_position}"
            )
            self.write_to_event_log(
                f"{light_engine.capitalize()} Keyence Drift: {focus_drift}"
            )

            self.coord_systems["keyence"][light_engine]["Focus"] = current_position
            self.coord_systems["light_engine"][light_engine]["Focus"] = (
                self.coord_systems["light_engine"][light_engine]["Focus"] - focus_drift
            )

            # get keyence offsets
            for measurement in list(self.keyence_measurement_list[light_engine]):
                measurement = measurement.split(", ")
                x_offset = float(measurement[0])
                y_offset = float(measurement[1])

                self.update_measurement_progress()

                move_all_galil(
                    log,
                    self.galil,
                    x_offset
                    + self.coord_systems["keyence"][light_engine]["X"],
                    y_offset
                    + self.coord_systems["keyence"][light_engine]["Y"],
                    None,
                    None,
                    # speed_x=25,
                )
                time.sleep(5.0)
                keyence_position = float(
                    self.keyence.read_all()[
                        keyence_indexes[light_engine]["measurement_index"] + 1
                    ]
                )
                self.keyence_measurement_list[light_engine][
                    f"{x_offset}, {y_offset}"
                ] = (start_position - keyence_position)

        self.update_measurement_progress()
        self.write_to_event_log(f"Keyence Focus Offsets: {self.keyence_measurement_list}")
        self.move_build_platform_down(self.default_position_settings)

    def pre_exposure_tasks(self, settings, light_engine):
        """Move X, Y, and Focus stages to exposure positions"""
        # convert light engine to screen light engine
        screen_light_engine = None
        for temp in config_dict["screen"]["light_engines"]:
            if temp in light_engine:
                screen_light_engine = temp
                break
        if screen_light_engine is None:
            log.error(
                "No matching light engine found in coord systems: '%s'", light_engine
            )

        defocus_um = settings["Relative focus position (um)"]
        x_offset = float(settings.get("Image x offset (um)", self.default_x_offset))
        y_offset = float(settings.get("Image y offset (um)", self.default_y_offset))

        # keyence correction
        base_focus = self.coord_systems["light_engine"][screen_light_engine]["Focus"]
        keyence_measurement = self.keyence_measurement_list[screen_light_engine][
            f"{x_offset}, {y_offset}"
        ]
        z_focus = base_focus + defocus_um + keyence_measurement
        self.galil_threads = move_all_galil(
            log,
            self.galil,
            x_offset + self.coord_systems["light_engine"][screen_light_engine]["X"],
            y_offset + self.coord_systems["light_engine"][screen_light_engine]["Y"],
            z_focus,
            None,
            join=False,
            # speed_x=25,
        )

        super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, settings, light_engine):
        """Join X, Y, and Focus threads"""
        for thread in self.galil_threads:
            if thread is not None:
                thread.join()
        return super().pre_exposure_joins(settings, light_engine)
