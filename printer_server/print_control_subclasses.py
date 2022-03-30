from printer_server.print_control import *


def move_all_galil(
    galil, x, y, z, bp, join=True, speed_x=50, speed_y=50, speed_z=25, speed_bp=25
):
    """
    Starts multithreaded movement on all of the galil axes. If any axis is set to none, it will not move.
    If join is set to true, the movements will join before returning
    """
    threads = [None, None, None, None]
    if x is not None:
        threads[0] = threading.Thread(
            target=galil.absMove,
            kwargs={"mm": x / 1000, "speed": speed_x, "axis": "X"},
        )
        threads[0].start()
    if y is not None:
        threads[1] = threading.Thread(
            target=galil.absMove,
            kwargs={"mm": y / 1000, "speed": speed_y, "axis": "Y"},
        )
        threads[1].start()
    if z is not None:
        threads[2] = threading.Thread(
            target=galil.absMove,
            kwargs={"mm": z / 1000, "speed": speed_z, "axis": "Focus"},
        )
        threads[2].start()

    if bp is not None:
        threads[3] = threading.Thread(
            target=galil.absMove,
            kwargs={"mm": bp / 1000, "speed": speed_bp, "axis": "Build Platform"},
        )
        threads[3].start()

    if join:
        for thread in threads:
            if thread is not None:
                thread.join()
    else:
        return threads


class HR3v3u_PrintControl(PrintControl):
    # from printer_server.drivers.kdc101.kdc101_snip import get_kdc_positions

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
        self.keyence_start_position = None
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

        galil_Z_thread = threading.Thread(target=self.galil_z_thread, args=[])
        galil_BP_thread = threading.Thread(target=self.galil_bp_thread, args=[])

        galil_Z_thread.start()
        galil_BP_thread.start()

        galil_Z_thread.join()
        galil_BP_thread.join()

    def galil_z_thread(self):
        self.galil.absMove(mm=self.focused_position / 1000, speed=50, axis="Focus")

    def galil_bp_thread(self):
        self.galil.goToZmax()

    def pre_print_tasks(self):
        """Move keyence sensor to all exposure positions and get focus offsets"""
        defaults_layer_settings = self.print_settings.get("Default layer settings")
        default_image_settings = defaults_layer_settings.get("Image settings")
        self.default_position_settings = defaults_layer_settings.get("Position settings")
        self.default_x_offset = default_image_settings.get("Image x offset (um)", 0)
        self.default_y_offset = default_image_settings.get("Image y offset (um)", 0)

        # check for keyence positions
        keyence_x_offset = -5777
        keyence_y_offset = -32169
        z_offset = self.focused_position - 750

        # time.sleep(1.0)
        # self.gpio.film_relay_on()
        self.move_build_platform_up(self.default_position_settings)
        time.sleep(1.0)
        x_offset = self.default_x_offset + keyence_x_offset
        y_offset = self.default_y_offset + keyence_y_offset
        move_all_galil(self.galil, x_offset, y_offset, z_offset, None)
        time.sleep(0.1)
        self.keyence_start_position = float(self.keyence.read_all()[1])

        self.keyence_measurement_list = {}
        for i, layer in enumerate(self.layer_map):
            current_layer_settings = self.print_settings["Layers"][layer[0]]
            image_settings_list = self.get_image_settings(current_layer_settings)
            for j, settings in enumerate(image_settings_list):
                x = settings.get("Image x offset (um)", self.default_x_offset)
                y = settings.get("Image y offset (um)", self.default_y_offset)
                if f"{x}, {y}" not in self.keyence_measurement_list:
                    move_all_galil(
                        self.galil, x + keyence_x_offset, y + keyence_y_offset, None, None
                    )
                    time.sleep(0.1)
                    self.keyence_measurement_list[f"{x}, {y}"] = float(
                        self.keyence.read_all()[1]
                    )
        # time.sleep(0.1)
        # self.gpio.film_relay_off()
        self.move_build_platform_down(self.default_position_settings)

    def post_print_tasks(self):
        """Move all galil stages to their starting positions"""

        # time.sleep(1.0)
        # self.gpio.film_relay_on()
        self.move_build_platform_up(self.default_position_settings)
        # time.sleep(0.1)
        # self.gpio.film_relay_off()
        move_all_galil(
            self.galil,
            self.default_x_offset,
            self.default_y_offset,
            self.focused_position,
            self.galil.top_position,
        )

    def pre_exposure_tasks(self, settings):
        """Move X, Y, and Focus stages to exposure positions"""
        defocus_um = settings["Relative focus position (um)"]
        x_offset = settings.get("Image x offset (um)", self.default_x_offset)
        y_offset = settings.get("Image y offset (um)", self.default_y_offset)

        # keyence correction
        keyence_measurement = self.keyence_measurement_list[f"{x_offset}, {y_offset}"]
        z_correction = self.keyence_start_position - keyence_measurement
        z_focus = self.focused_position + defocus_um + z_correction * 1000

        self.galil_threads = move_all_galil(
            self.galil, x_offset, y_offset, z_focus, None, join=False
        )
        return super().pre_exposure_tasks(settings)

    def pre_exposure_joins(self):
        """Join X, Y, and Focus threads"""
        for thread in self.galil_threads:
            if thread is not None:
                thread.join()
        return super().pre_exposure_joins()


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


class HR4Film_PrintControl(HR3v3u_PrintControl, GPIO_PrintControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        return super().initialize(run_in_thread=False)


# def galil_setup_thread(self):
#     """Initialize and home Galil controller"""
#     self.galil.connect()
#     self.galil.initialize()
#     self.galil.home()

#     # galil_X_thread = threading.Thread(target=self.galil_x_thread, args=[])
#     # galil_Y_thread = threading.Thread(target=self.galil_y_thread, args=[])
#     galil_Z_thread = threading.Thread(target=self.galil_z_thread, args=[])
#     galil_BP_thread = threading.Thread(target=self.galil_bp_thread, args=[])

#     # galil_X_thread.start()
#     # galil_Y_thread.start()
#     galil_Z_thread.start()
#     galil_BP_thread.start()

#     # galil_X_thread.join()
#     # galil_Y_thread.join()
#     galil_Z_thread.join()
#     galil_BP_thread.join()

# # def galil_x_thread(self):
# #      # self.galil.absMove(cnts=-4800000, speed=100, axis="X") # Visitech
# #     # self.galil.absMove(cnts=7232000, speed=100, axis="X") # Wintech
# #     # self.galil.absMove(cnts=-500000, speed=100, axis="X") # Keyence

# # def galil_y_thread(self):
# #     # self.galil.absMove(mm=0, speed=50, axis="Y")
# #     self.galil.absMove(mm=5, speed=50, axis="Y")
