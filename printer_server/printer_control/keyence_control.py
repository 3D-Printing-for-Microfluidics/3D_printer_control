from printer_server.printer_control.print_control import *

class KeyenceControl(XYControl, FocusControl):
    def __init__(self):
        super().__init__()
        self.keyence = driver_handles.keyence
        self.keyence_measurement_list = None

        self.default_position_settings = None
        self.default_x_offset = None
        self.default_y_offset = None
        self.default_light_engine = None

    def connect_hardware(self):
        keyence_thread = Thread(log, name="keyence_control_setup_thread", target=self.keyence.connect, args=[])
        keyence_thread.start()
        super().connect_hardware()
        keyence_thread.join()
        if not self.keyence.connected:
            self.all_hardware_connected = False

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

        # Move focus around a little bit before print. Seems to help repeatablility
        for light_engine in config_dict["screen"]["light_engines"]:
            self.focus_stage.absMoveFocus(self.coord_systems[f"keyence_{light_engine}"]["Focus"])
            time.sleep(1.0)

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
            start_position = get_last_calibration_positions_from_logs()[f"keyence_{sensor}"]
            self.write_to_event_log(
                f"{light_engine.capitalize()} Keyence Target Position: {start_position}"
            )
            # goto position
            x_pos = self.default_x_offset/1000 + self.coord_systems[f"keyence_{light_engine}"]["X"]
            y_pos = self.default_y_offset/1000 + self.coord_systems[f"keyence_{light_engine}"]["Y"]
            focus_pos = self.coord_systems[f"keyence_{light_engine}"]["Focus"]
            xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False)
            focus_thread = self.focus_stage.threadedFocusMove(log, focus_pos, join=False)
            for thread in xy_threads:
                if thread is not None:
                    thread.join()
            if focus_thread is not None:
                focus_thread.join()
            time.sleep(5.0)

            # get keyence reading
            temp_position = float(
                self.keyence.read_all()[
                    keyence_indexes[light_engine]["measurement_index"] + 1
                ]
            )

            self.update_measurement_progress()

            focus_pos = self.coord_systems[f"keyence_{light_engine}"]["Focus"] + (start_position - temp_position)/1000
            self.focus_stage.absMoveFocus(focus_pos):
            time.sleep(1.0)

            temp_position = float(
                self.keyence.read_all()[
                    keyence_indexes[light_engine]["measurement_index"] + 1
                ]
            )
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
                self.xy_stage.threadedXYMove(log, x_pos, y_pos)
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

    def convert_le_to_screen_le(self, light_engine)
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
        return screen_light_engine

    def get_exposure_defocus_position(self, settings, light_engine):
        screen_light_engine = self.convert_le_to_screen_le(light_engine)
        self.focused_position = self.coord_systems[screen_light_engine]["Focus"]

        defocus_um = settings["Relative focus position (um)"]
        x_offset = float(settings.get("Image x offset (um)", self.default_x_offset))
        y_offset = float(settings.get("Image y offset (um)", self.default_y_offset))

        # keyence correction
        keyence_measurement = self.keyence_measurement_list[screen_light_engine][
            f"{x_offset}, {y_offset}"
        ]

        self.defocus_um = (defocus_um + keyence_measurement)/1000

    def pre_exposure_tasks(self, settings, light_engine):
        """Move X, Y, and Focus stages to exposure positions"""
        x_offset = float(settings.get("Image x offset (um)", self.default_x_offset))
        y_offset = float(settings.get("Image y offset (um)", self.default_y_offset))
        screen_light_engine = self.convert_le_to_screen_le(light_engine)

        x_pos = x_offset + self.coord_systems[screen_light_engine]["X"]
        y_pos =  y_offset + self.coord_systems[screen_light_engine]["Y"]
        self.xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False)

        super().pre_exposure_tasks(settings, light_engine)

    def pre_exposure_joins(self, light_engine):
        """Join X, Y, and Focus threads"""
        for thread in self.xy_threads:
            if thread is not None:
                thread.join()
        return super().pre_exposure_joins(light_engine)

    def post_print_tasks(self):
        self.focused_position = self.coord_systems["visitech"]["Focus"]
        super().post_print_tasks()

    # def xy_keyence_alignment(self):
    #     edges = {
    #         "visitech": {"X": [-45515, 42500], "Y": [-28871, 33500]},
    #         "wintech": {"X": [-45576, 42500], "Y": [-28800, 33500]},
    #         "diff": {"X": [0, 0, 0], "Y": [0, 0, 0]},
    #     }

    #     keyence_indexes = config_dict["keyence"]["sensors"]

    #     for light_engine in config_dict["screen"]["light_engines"]:
    #         for axis in ("X", "Y"):
    #             # for direction_indx in (0, 1):
    #             for step_size in (1000.0, 100.0, 10.0):
    #                 direction_indx = 1
    #                 direction = (-1, 1)
    #                 direction = direction[direction_indx]
    #                 step_size = step_size * direction

    #                 # calculate xy positions
    #                 x_offset = 0
    #                 y_offset = 0
    #                 if axis == "X":
    #                     x_offset = edges[light_engine]["X"][direction_indx] - step_size
    #                 else:
    #                     y_offset = edges[light_engine]["Y"][direction_indx] - step_size

    #                 # goto apx position
    #                 time.sleep(0.1)
    #                 x_pos = self.coord_systems[f"keyence_{light_engine}"]["X"] + x_offset/1000
    #                 y_pos = self.coord_systems[f"keyence_{light_engine}"]["Y"] + y_offset/1000
    #                 focus_pos = self.coord_systems[f"keyence_{light_engine}"]["Focus"]
    #                 xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False, speed_x=None, speed_y=None, acceleration_x=None, acceleration_y=None)
    #                 focus_thread = self.focus_stage.threadedFocusMove(log, focus_pos, join=False, speed=None, acceleration=None)
    #                 for thread in xy_threads:
    #                     if thread is not None:
    #                         thread.join()
    #                 if focus_thread is not None:
    #                     focus_thread.join()

    #                 if step_size == 1000.0:
    #                     time.sleep(5)
    #                 else:
    #                     time.sleep(0.1)

    #                 # find resin tray edge
    #                 self.xy_stage.startXYJog(
    #                     speed=step_size / 1000.0, acceleration=50, axis=axis
    #                 )
    #                 last_keyence_position = float(
    #                     self.keyence.read_all()[
    #                         keyence_indexes[light_engine]["measurement_index"] + 1
    #                     ]
    #                 )
    #                 while True:
    #                     keyence_position = float(
    #                         self.keyence.read_all()[
    #                             keyence_indexes[light_engine]["measurement_index"] + 1
    #                         ]
    #                     )
    #                     if abs(keyence_position - last_keyence_position) > 2:
    #                         break

    #                     last_keyence_position = keyence_position

    #                     time.sleep(0.001)

    #                 # save resin tray edge
    #                 edges[light_engine][axis][direction_indx] = (
    #                     self.xy_stage.getXYPosition(axis=axis)
    #                     * 1000
    #                     - self.coord_systems[f"keyence_{light_engine}"][axis]
    #                 )

    #                 self.xy_stage.stopXYJog(axis=axis)
    #                 time.sleep(0.1)

    #     for axis in ("X", "Y"):
    #         for direction_indx in (0, 1):
    #             edges["diff"][axis][direction_indx] = (
    #                 edges["visitech"][axis][direction_indx]
    #                 - edges["wintech"][axis][direction_indx]
    #             )

    #     self.coord_systems["keyence_visitech"]["X"] += edges["diff"]["X"][1]
    #     self.coord_systems["keyence_visitech"]["Y"] += edges["diff"]["Y"][1]
    #     self.coord_systems["visitech"]["X"] += edges["diff"]["X"][1]
    #     self.coord_systems["visitech"]["Y"] += edges["diff"]["Y"][1]

    # def initalize_hardware(self):
    #     super().initalize_hardware()
    #     # self.xy_keyence_alignment()