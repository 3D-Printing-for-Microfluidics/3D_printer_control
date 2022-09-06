from printer_server.print_control import *


def move_all_galil(
    galil,
    x,
    y,
    z,
    bp,
    join=True,
    speed_x=50,
    speed_y=50,
    speed_z=25,
    speed_bp=25,
    acceleration_x=50,
    acceleration_y=50,
    acceleration_z=50,
    acceleration_bp=50,
):
    """
    Starts multithreaded movement on all of the galil axes. If any axis is set to none, it will not move.
    If join is set to true, the movements will join before returning
    """
    threads = [None, None, None, None]
    if x is not None:
        threads[0] = threading.Thread(
            target=galil.absMove,
            kwargs={
                "mm": x / 1000,
                "speed": speed_x,
                "acceleration": acceleration_x,
                "axis": "X",
            },
        )
        threads[0].start()
    if y is not None:
        threads[1] = threading.Thread(
            target=galil.absMove,
            kwargs={
                "mm": y / 1000,
                "speed": speed_y,
                "acceleration": acceleration_y,
                "axis": "Y",
            },
        )
        threads[1].start()
    if z is not None:
        threads[2] = threading.Thread(
            target=galil.absMove,
            kwargs={
                "mm": z / 1000,
                "speed": speed_z,
                "acceleration": acceleration_z,
                "axis": "Focus",
            },
        )
        threads[2].start()

    if bp is not None:
        threads[3] = threading.Thread(
            target=galil.absMove,
            kwargs={
                "mm": bp / 1000,
                "speed": speed_bp,
                "acceleration": acceleration_bp,
                "axis": "Build Platform",
            },
        )
        threads[3].start()

    if join:
        for thread in threads:
            if thread is not None:
                thread.join()
    else:
        return threads


def get_keyence_position(sensor):
    """Return the last focused position for the keyence sensor from the
    position log file.
    """
    return get_last_calibration_positions()[f"keyence_{sensor}"]


class HR3v3u_PrintControl(PrintControl):
    def __init__(self):
        """Create KDC handle"""
        super().__init__()
        self.kdc = driver_handles.kdc
        self.kdc_thread = None
        self.defocus_um = None

    def get_focus(self):
        """Return KDC position"""
        return self.kdc.getCurrentPos()

    def change_focus(self, pos):
        """Move KDC stage to position"""
        self.write_to_event_log("Start Distance Movement")
        self.kdc.move(pos, relative=False)
        self.write_to_event_log("Finish Distance Movement")

    def kdc_setup_thread(self):
        """Initialize and home ThorLabs stage"""
        self.kdc.connect()
        if not self.kdc.homed:
            self.kdc.home()
            self.kdc.move(self.focused_position, relative=False)

    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        """Start KDC setup thread"""
        if self.state == "uninitialized":
            self.kdc_thread = threading.Thread(target=self.kdc_setup_thread, args=[])
            self.kdc_thread.start()
            super().initialize(run_in_thread=False)
            self.kdc_thread.join()
            log.info("Printer initialized, all hardware ready.")

    def post_print_tasks(self):
        """Move BP stage up 'Distance up (mm)'' then to top"""
        super().post_print_tasks()
        defaults_layer_settings = self.print_settings.get("Default layer settings")
        default_position_settings = defaults_layer_settings.get("Position settings")

        self.move_build_platform_up(default_position_settings)
        self.galil.goToZmax()
        time.sleep(1.0)

    def pre_exposure_tasks(self, settings):
        """If layer is defocused, move KDC and shift image"""
        self.defocus_um = settings["Relative focus position (um)"]
        if self.defocus_um != 0:
            self.kdc_thread = threading.Thread(
                target=self.change_focus,
                args=[self.focused_position + self.defocus_um],
            )
            self.kdc_thread.start()
            self.image = shift_image(self.image, x=um_to_px(self.defocus_um))
        return super().pre_exposure_tasks(settings)

    def pre_exposure_joins(self):
        """If layer is defocused, wait for KDC thread to finish"""
        if self.defocus_um != 0:
            self.kdc_thread.join()
        return super().pre_exposure_joins()

    def post_exposure_tasks(self):
        """If layer is defocused, return KDC to focus position"""
        # fix focus if this exposure was defocused
        if self.defocus_um != 0:
            self.change_focus(self.focused_position)


class HR4_PrintControl(PrintControl):
    def __init__(self):
        """Create keyence handle"""
        super().__init__()
        self.keyence = driver_handles.keyence
        self.coord_systems = {
            "keyence": {
                "visitech": config_dict["galil"]["coord_systems"]["keyence_visitech"]
            },
            "light_engine": {
                "visitech": config_dict["galil"]["coord_systems"]["visitech"]
            },
        }
        self.keyence_measurement_list = None

        self.default_position_settings = None
        self.default_x_offset = None
        self.default_y_offset = None

        self.galil_threads = None

    def get_focus(self):
        """Return galil 'Focus' axis position"""
        return int(
            self.galil.cntsToMm(self.galil.getPosition(axis="Focus"), axis="Focus") * 1000
        )

    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        """Initialize keyence sensor"""
        if self.state == "uninitialized":
            keyence_thread = threading.Thread(target=self.keyence.connect, args=[])
            keyence_thread.start()
            super().initialize(run_in_thread=False)
            keyence_thread.join()
            log.info("Printer initialized, all hardware ready.")

    def galil_setup_thread(self):
        """Initialize and home Galil controller"""
        self.galil.connect()
        self.galil.initialize()
        self.galil.home()

        move_all_galil(
            self.galil,
            self.coord_systems["light_engine"]["visitech"]["X"],
            self.coord_systems["light_engine"]["visitech"]["Y"],
            self.coord_systems["light_engine"]["visitech"]["Focus"],
            self.galil.cntsToMm(self.galil.top_position, axis="Focus") * 1000,
        )

    def pre_print_tasks(self):
        """Move keyence sensor to all exposure positions and get focus offsets"""
        defaults_layer_settings = self.print_settings.get("Default layer settings")
        default_image_settings = defaults_layer_settings.get("Image settings")
        self.default_position_settings = defaults_layer_settings.get("Position settings")
        self.default_x_offset = default_image_settings.get("Image x offset (um)", 0)
        self.default_y_offset = default_image_settings.get("Image y offset (um)", 0)

        # check for keyence positions
        keyence_index = (
            config_dict["keyence"]["sensors"]["visitech"]["measurement_index"] + 1
        )

        self.move_build_platform_up(self.default_position_settings)
        time.sleep(1.0)

        keyence_start_position = get_keyence_position("visitech")
        self.write_to_event_log(
            f"Visitech Keyence Target Focus Position: {keyence_start_position}"
        )
        # goto position
        move_all_galil(
            self.galil,
            self.default_x_offset + self.coord_systems["keyence"]["visitech"]["X"],
            self.default_y_offset + self.coord_systems["keyence"]["visitech"]["Y"],
            self.coord_systems["keyence"]["visitech"]["Focus"],
            None,
        )
        time.sleep(1.0)
        # get keyence reading
        temp_position = float(self.keyence.read_all()[keyence_index])
        move_all_galil(
            self.galil,
            None,
            None,
            self.coord_systems["keyence"]["visitech"]["Focus"]
            + (keyence_start_position - temp_position),
            None,
        )
        time.sleep(1.0)
        temp_position = float(self.keyence.read_all()[keyence_index])
        self.write_to_event_log(
            f"Visitech Keyence Actual Focus Position: {temp_position}"
        )
        current_position = (
            self.galil.cntsToMm(self.galil.getPosition(axis="Focus"), axis="Focus") * 1000
        )
        focus_drift = (
            self.coord_systems["keyence"]["visitech"]["Focus"] - current_position
        )

        self.coord_systems["keyence"]["visitech"]["Focus"] = current_position
        self.coord_systems["light_engine"]["visitech"]["Focus"] = (
            self.coord_systems["light_engine"]["visitech"]["Focus"] - focus_drift
        )

        self.keyence_measurement_list = {}
        for i, layer in enumerate(self.layer_map):
            current_layer_settings = self.print_settings["Layers"][layer[0]]
            image_settings_list = self.get_image_settings(current_layer_settings)
            for j, settings in enumerate(image_settings_list):
                x_offset = settings.get("Image x offset (um)", self.default_x_offset)
                y_offset = settings.get("Image y offset (um)", self.default_y_offset)
                if f"{x_offset}, {y_offset}" not in self.keyence_measurement_list:
                    move_all_galil(
                        self.galil,
                        x_offset + self.coord_systems["keyence"]["visitech"]["X"],
                        y_offset + self.coord_systems["keyence"]["visitech"]["Y"],
                        None,
                        None,
                    )
                    time.sleep(0.1)
                    keyence_position = float(self.keyence.read_all()[keyence_index])
                    self.keyence_measurement_list[f"{x_offset}, {y_offset}"] = (
                        keyence_start_position - keyence_position
                    )
        self.write_to_event_log(f"Keyence Focus Offsets: {self.keyence_measurement_list}")
        self.move_build_platform_down(self.default_position_settings)

    def post_print_tasks(self):
        """Move all galil stages to their starting positions"""
        super().post_print_tasks()

        self.move_build_platform_up(self.default_position_settings)
        move_all_galil(
            self.galil,
            self.coord_systems["light_engine"]["visitech"]["X"],
            self.coord_systems["light_engine"]["visitech"]["Y"],
            self.coord_systems["light_engine"]["visitech"]["Focus"],
            self.galil.top_position,
        )

    def pre_exposure_tasks(self, settings):
        """Move X, Y, and Focus stages to exposure positions"""
        defocus_um = settings["Relative focus position (um)"]
        x_offset = settings.get("Image x offset (um)", self.default_x_offset)
        y_offset = settings.get("Image y offset (um)", self.default_y_offset)

        # keyence correction
        keyence_measurement = self.keyence_measurement_list[f"{x_offset}, {y_offset}"]
        z_focus = (
            self.coord_systems["light_engine"]["visitech"]["Focus"]
            + defocus_um
            + keyence_measurement
        )

        self.galil_threads = move_all_galil(
            self.galil,
            x_offset + self.coord_systems["light_engine"]["visitech"]["X"],
            y_offset + self.coord_systems["light_engine"]["visitech"]["Y"],
            z_focus,
            None,
            join=False,
        )
        return super().pre_exposure_tasks(settings)

    def pre_exposure_joins(self):
        """Join X, Y, and Focus threads"""
        for thread in self.galil_threads:
            if thread is not None:
                thread.join()
        return super().pre_exposure_joins()


class MR1v1_PrintControl(HR4_PrintControl):
    def __init__(self):
        """Create wintech handle"""
        super().__init__()
        self.gpio = driver_handles.gpio
        self.wintech_thread = None
        self.wintech = driver_handles.wintech
        self.default_light_engine = None
        self.coord_systems = {
            "keyence": {
                "visitech": config_dict["galil"]["coord_systems"]["keyence_visitech"],
                "wintech": config_dict["galil"]["coord_systems"]["keyence_wintech"],
            },
            "light_engine": {
                "visitech": config_dict["galil"]["coord_systems"]["visitech"],
                "wintech": config_dict["galil"]["coord_systems"]["wintech"],
            },
        }

    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        if self.state == "uninitialized":
            gpio_thread = threading.Thread(target=self.gpio.initialize, args=[])
            gpio_thread.start()
            self.wintech_thread = threading.Thread(target=self.wintech.connect, args=[])
            self.wintech_thread.start()
            super().initialize(run_in_thread=False)
            gpio_thread.join()
            self.wintech_thread.join()
            log.info("Printer initialized, all hardware ready.")

    # def galil_setup_thread(self):
    #     """Initialize and home Galil controller"""
    #     self.galil.connect()
    #     self.galil.initialize()
    #     self.galil.home()

    #     move_all_galil(
    #         self.galil,
    #         self.coord_systems["light_engine"]["visitech"]["X"],
    #         self.coord_systems["light_engine"]["visitech"]["Y"],
    #         self.coord_systems["light_engine"]["visitech"]["Focus"],
    #         self.galil.cntsToMm(self.galil.top_position, axis="Focus") * 1000,
    #         speed_x=100,
    #         speed_y=100,
    #         acceleration_x=400,
    #         acceleration_y=400,
    #     )

    def pre_print_tasks(self):
        """Move keyence sensor to all exposure positions and get focus offsets"""
        defaults_layer_settings = self.print_settings.get("Default layer settings")
        default_image_settings = defaults_layer_settings.get("Image settings")
        self.default_position_settings = defaults_layer_settings.get("Position settings")
        self.default_x_offset = default_image_settings.get("Image x offset (um)", 0)
        self.default_y_offset = default_image_settings.get("Image y offset (um)", 0)
        self.default_light_engine = default_image_settings.get("Light engine", "visitech")

        keyence_indexes = config_dict["keyence"]["sensors"]
        self.keyence_measurement_list = {}

        self.move_build_platform_up(self.default_position_settings)
        time.sleep(1.0)

        # move focus stage around a little to settle better
        for light_engine in config_dict["screen"]["light_engines"]:
            move_all_galil(
                self.galil,
                None,
                None,
                self.coord_systems["keyence"][light_engine]["Focus"],
                None,
                speed_x=25,
            )
            time.sleep(1.0)

        self.gpio.fan_relay_on()
        for light_engine in config_dict["screen"]["light_engines"]:
            # load keyence focal position
            start_position = get_keyence_position(light_engine)
            self.write_to_event_log(
                f"{light_engine.capitalize()} Keyence Target Focus Position: {start_position}"
            )
            # goto position
            move_all_galil(
                self.galil,
                self.default_x_offset + self.coord_systems["keyence"][light_engine]["X"],
                self.default_y_offset + self.coord_systems["keyence"][light_engine]["Y"],
                self.coord_systems["keyence"][light_engine]["Focus"],
                None,
                speed_x=25,
            )
            time.sleep(1.0)
            # get keyence reading
            temp_position = float(
                self.keyence.read_all()[
                    keyence_indexes[light_engine]["measurement_index"] + 1
                ]
            )
            move_all_galil(
                self.galil,
                None,
                None,
                self.coord_systems["keyence"][light_engine]["Focus"]
                + (start_position - temp_position),
                None,
                speed_x=25,
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
            print(f"Drift: {focus_drift}")
            self.write_to_event_log(
                f"{light_engine.capitalize()} Keyence Actual Focus Position: {temp_position}"
            )

            self.coord_systems["keyence"][light_engine]["Focus"] = current_position
            self.coord_systems["light_engine"][light_engine]["Focus"] = (
                self.coord_systems["light_engine"][light_engine]["Focus"] - focus_drift
            )

            # get keyence offsets
            for i, layer in enumerate(self.layer_map):
                current_layer_settings = self.print_settings["Layers"][layer[0]]
                image_settings_list = self.get_image_settings(current_layer_settings)
                for j, settings in enumerate(image_settings_list):
                    x_offset = settings.get("Image x offset (um)", self.default_x_offset)
                    y_offset = settings.get("Image y offset (um)", self.default_y_offset)
                    layer_light_engine = settings.get(
                        "Light engine", self.default_light_engine
                    )
                    if layer_light_engine == light_engine:
                        if (
                            f"{light_engine} {x_offset}, {y_offset}"
                            not in self.keyence_measurement_list
                        ):
                            move_all_galil(
                                self.galil,
                                x_offset
                                + self.coord_systems["keyence"][light_engine]["X"],
                                y_offset
                                + self.coord_systems["keyence"][light_engine]["Y"],
                                None,
                                None,
                                speed_x=25,
                            )
                            time.sleep(1.0)
                            keyence_position = float(
                                self.keyence.read_all()[
                                    keyence_indexes[light_engine]["measurement_index"] + 1
                                ]
                            )
                            self.keyence_measurement_list[
                                f"{light_engine} {x_offset}, {y_offset}"
                            ] = (start_position - keyence_position)

        self.gpio.fan_relay_off()

        self.write_to_event_log(f"Keyence Focus Offsets: {self.keyence_measurement_list}")
        self.move_build_platform_down(self.default_position_settings)

    def post_print_tasks(self):
        # always turn off the Visitech
        self.wintech.stop_sequencer()
        home.update_wintech_led_status(False)
        self.gpio.fan_relay_off()
        self.screen.clear(screen=config_dict["screen"]["light_engines"].index("wintech"))

        self.move_build_platform_up(self.default_position_settings)
        move_all_galil(
            self.galil,
            self.coord_systems["light_engine"]["visitech"]["X"],
            self.coord_systems["light_engine"]["visitech"]["Y"],
            self.coord_systems["light_engine"]["visitech"]["Focus"],
            self.galil.top_position,
            speed_x=25,
        )

        PrintControl.post_print_tasks(self)

        # keyence_indexes = config_dict["keyence"]["sensors"]
        # for light_engine in config_dict["screen"]["light_engines"]:
        #     # get home keyence reading
        #     move_all_galil(
        #         self.galil,
        #         self.default_x_offset + self.coord_systems["keyence"][light_engine]["X"],
        #         self.default_y_offset + self.coord_systems["keyence"][light_engine]["Y"],
        #         self.coord_systems["keyence"][light_engine]["Focus"],
        #         None,
        #     )
        #     time.sleep(1.0)
        #     self.write_to_event_log(
        #         f"{light_engine.capitalize()} Keyence Focus Position: {float(self.keyence.read_all()[keyence_indexes[light_engine]['measurement_index'] + 1])}"
        #     )

    def pre_exposure_tasks(self, settings, light_engine):
        """Move X, Y, and Focus stages to exposure positions"""
        defocus_um = settings["Relative focus position (um)"]
        x_offset = settings.get("Image x offset (um)", self.default_x_offset)
        y_offset = settings.get("Image y offset (um)", self.default_y_offset)
        screen_index = config_dict["screen"]["light_engines"].index(light_engine)

        # keyence correction
        base_focus = self.coord_systems["light_engine"][light_engine]["Focus"]
        keyence_measurement = self.keyence_measurement_list[
            f"{light_engine} {x_offset}, {y_offset}"
        ]
        z_focus = base_focus + defocus_um + keyence_measurement
        self.galil_threads = move_all_galil(
            self.galil,
            x_offset + self.coord_systems["light_engine"][light_engine]["X"],
            y_offset + self.coord_systems["light_engine"][light_engine]["Y"],
            z_focus,
            None,
            join=False,
            speed_x=25,
        )

        # screen thread
        self.screen_thread = threading.Thread(
            target=self.screen.draw,
            args=[self.image],
            kwargs={"screen": screen_index},
        )
        self.screen_thread.start()

        self.write_to_event_log("Setup Exposure")
        if light_engine == "wintech":
            # wintech setup thread
            self.wintech_thread = threading.Thread(
                target=self.wintech.setup_exposure,
                args=[self.exposure_time_ms, self.power],
            )
            self.wintech_thread.start()

            if self.gpio.fan_relay_state == False:
                self.gpio.fan_relay_on()
        else:
            # visitech setup thread
            self.visitech_thread = threading.Thread(
                target=self.visitech.setup_exposure,
                args=[self.exposure_time_ms, self.power],
            )
            self.visitech_thread.start()

            if self.gpio.fan_relay_state == True:
                self.gpio.fan_relay_off()

    def pre_exposure_joins(self, light_engine):
        """Join X, Y, and Focus threads"""
        for thread in self.galil_threads:
            if thread is not None:
                thread.join()

        # wait for all hardware to be ready for exposure
        if not self.next_layer == 1:
            self.galil_thread.join()
        self.screen_thread.join()
        if light_engine == "wintech":
            self.wintech_thread.join()
        else:
            self.visitech_thread.join()

    def exposure_worker(self, j, settings, exposure_data):
        """Process a single exposure of the 3D print.

        This method should only be called from inside layer_worker.
        """
        # read settings for this exposure
        slices_folder = Path(self.print_settings["Header"]["Image directory"])
        self.image = self.current_job / slices_folder / Path(settings["Image file"])
        self.exposure_time_ms = settings["Layer exposure time (ms)"]
        self.power = settings["Light engine power setting"]
        light_engine = settings.get("Light engine", "visitech")
        layer_start_position = self.get_focus()

        # run pre-exposure tasks
        self.pre_exposure_tasks(settings, light_engine)
        self.pre_exposure_joins(light_engine)

        if light_engine == "wintech":
            position_during_exposure = self.get_focus()
            pre_exposure_status = ""
            time.sleep(settings["Wait before exposure (ms)"] / 1000)
            self.write_to_event_log("Start Exposure")
            home.update_wintech_led_status(True)
            self.wintech.perform_exposure()
            home.update_wintech_led_status(False)
            self.write_to_event_log("Finish Exposure")
            time.sleep(settings["Wait after exposure (ms)"] / 1000)

            self.post_exposure_tasks()
            post_exposure_status = ""

        else:
            # do the exposure
            position_during_exposure = self.get_focus()
            pre_exposure_status = self.visitech.read_all_status()
            time.sleep(settings["Wait before exposure (ms)"] / 1000)
            self.write_to_event_log("Start Exposure")
            home.update_visitech_led_status(True)
            self.visitech.perform_exposure()
            home.update_visitech_led_status(False)
            self.write_to_event_log("Finish Exposure")
            time.sleep(settings["Wait after exposure (ms)"] / 1000)

            self.post_exposure_tasks()

            # Suppress the first Visitech OCP error. This appears to always be
            # triggered on the first exposure of each print job. It would be better
            # to figure out why this happens in the hardware and fix it there.
            if self.suppress_visitech_ocp_error:
                self.suppress_visitech_ocp_error = False  # only do this once per print
                for e in self.visitech.get_sticky_errors(warn=False):
                    if e and e.lower() != "led over current protection triggered":
                        log.warning("Visitech error: %s", e)  # report other errors
            post_exposure_status = self.visitech.read_all_status()

        # save expoure data
        exposure_data[j] = {
            "image": self.image.name,
            "power setting": self.power,
            "exposure time (ms)": self.exposure_time_ms,
            "layer starting position": layer_start_position,
            "position during exposure": position_during_exposure,
            "post exposure position": self.get_focus(),
            "pre exposure status": pre_exposure_status,
            "post exposure status": post_exposure_status,
        }


class GPIO_PrintControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.gpio = driver_handles.gpio

    def move_build_platform_up(self, position_settings):
        self.gpio.film_relay_on()
        super().move_build_platform_up(position_settings)
        self.gpio.film_relay_off()

    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        if self.state == "uninitialized":
            gpio_thread = threading.Thread(target=self.gpio.initialize, args=[])
            gpio_thread.start()
            super().initialize(run_in_thread=run_in_thread)
            gpio_thread.join()


class HR3v3_PrintControl(HR3v3u_PrintControl, GPIO_PrintControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        return super().initialize(run_in_thread=False)


class HR4Film_PrintControl(HR4_PrintControl, GPIO_PrintControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        return super().initialize(run_in_thread=False)
