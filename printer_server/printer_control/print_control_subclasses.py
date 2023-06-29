from printer_server.printer_control.print_control import *
from printer_server.printer_control.visitech_control import *
from printer_server.printer_control.wintech_control import *
from printer_server.printer_control.gpio_control import *
from printer_server.printer_control.keyence_control import *
from printer_server.printer_control.screen_control import *
from printer_server.printer_control.kdc_control import *


class HR3v3u_PrintControl(KDCControl, VisitechControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        if self.state == "uninitialized":
            super().initialize(run_in_thread=False)
            if run_in_thread:
                log.info("Printer initialized, all hardware ready.")

    def post_print_tasks(self):
        """Move BP stage up 'Distance up (mm)'' then to top"""
        super().post_print_tasks()
        defaults_layer_settings = self.print_settings.get("Default layer settings")
        default_position_settings = defaults_layer_settings.get("Position settings")

        self.move_build_platform_up(default_position_settings)
        self.galil.goToZmax()
        time.sleep(1.0)


class HR4_PrintControl(VisitechControl, KeyenceControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        if self.state == "uninitialized":
            super().initialize(run_in_thread=False)
            if run_in_thread:
                log.info("Printer initialized, all hardware ready.")

    def __init__(self):
        super().__init__()
        self.coord_systems = {
            "keyence": {
                "visitech": config_dict["galil"]["coord_systems"]["keyence_visitech"]
            },
            "light_engine": {
                "visitech": config_dict["galil"]["coord_systems"]["visitech"]
            },
        }
        self.default_position_settings = None
        self.default_x_offset = None
        self.default_y_offset = None

        self.galil_threads = None

    def get_focus(self):
        """Return galil 'Focus' axis position"""
        return int(
            self.galil.cntsToMm(self.galil.getPosition(axis="Focus"), axis="Focus") * 1000
        )

    def galil_finalize_setup_thread(self):
        move_all_galil(
            self.galil,
            self.coord_systems["light_engine"]["visitech"]["X"],
            self.coord_systems["light_engine"]["visitech"]["Y"],
            self.coord_systems["light_engine"]["visitech"]["Focus"],
            self.galil.cntsToMm(self.galil.top_position, axis="Focus") * 1000,
        )

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


class MR1v1_PrintControl(HR4_PrintControl, WintechControl, VisitechFanGPIOControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        if self.state == "uninitialized":
            super().initialize(run_in_thread=False)
            if run_in_thread:
                log.info("Printer initialized, all hardware ready.")

    def __init__(self):
        super().__init__()
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

    # def galil_keyence_alignment(self):
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

    #                 # calculate galil positions
    #                 x_offset = 0
    #                 y_offset = 0
    #                 if axis == "X":
    #                     x_offset = edges[light_engine]["X"][direction_indx] - step_size
    #                 else:
    #                     y_offset = edges[light_engine]["Y"][direction_indx] - step_size

    #                 # goto apx position
    #                 time.sleep(0.1)
    #                 move_all_galil(
    #                     self.galil,
    #                     self.coord_systems["keyence"][light_engine]["X"] + x_offset,
    #                     self.coord_systems["keyence"][light_engine]["Y"] + y_offset,
    #                     self.coord_systems["keyence"][light_engine]["Focus"],
    #                     None,
    #                 )
    #                 if step_size == 1000.0:
    #                     time.sleep(5)
    #                 else:
    #                     time.sleep(0.1)

    #                 # find resin tray edge
    #                 self.galil.startJog(
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
    #                     self.galil.cntsToMm(self.galil.getPosition(axis=axis), axis=axis)
    #                     * 1000
    #                     - self.coord_systems["keyence"][light_engine][axis]
    #                 )

    #                 self.galil.stopJog(axis=axis)
    #                 time.sleep(0.1)

    #     for axis in ("X", "Y"):
    #         for direction_indx in (0, 1):
    #             edges["diff"][axis][direction_indx] = (
    #                 edges["visitech"][axis][direction_indx]
    #                 - edges["wintech"][axis][direction_indx]
    #             )

    #     self.coord_systems["keyence"]["visitech"]["X"] += edges["diff"]["X"][1]
    #     self.coord_systems["keyence"]["visitech"]["Y"] += edges["diff"]["Y"][1]
    #     self.coord_systems["light_engine"]["visitech"]["X"] += edges["diff"]["X"][1]
    #     self.coord_systems["light_engine"]["visitech"]["Y"] += edges["diff"]["Y"][1]

    def galil_setup_thread(self):
        """Initialize and home Galil controller"""
        super().galil_setup_thread()

        # self.galil_keyence_alignment()

    def pre_print_tasks(self):
        for light_engine in config_dict["screen"]["light_engines"]:
            move_all_galil(
                self.galil,
                None,
                None,
                self.coord_systems["keyence"][light_engine]["Focus"],
                None,
            )
            time.sleep(1.0)
        super().pre_print_tasks()


class HR3v3_PrintControl(HR3v3u_PrintControl, FilmGPIOControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        super().initialize(run_in_thread=False)
        if run_in_thread:
            log.info("Printer initialized, all hardware ready.")


class HR4Film_PrintControl(HR4_PrintControl, FilmGPIOControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        super().initialize(run_in_thread=False)
        if run_in_thread:
            log.info("Printer initialized, all hardware ready.")
