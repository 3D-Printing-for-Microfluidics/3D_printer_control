from printer_server.printer_control.print_control import *
from printer_server.printer_control.visitech_control import *
from printer_server.printer_control.wintech_control import *
from printer_server.printer_control.gpio_control import *
from printer_server.printer_control.keyence_control import *
from printer_server.printer_control.screen_control import *
from printer_server.printer_control.kdc_control import *
from printer_server.printer_control.loadcell_control import *


class HR3v3u_PrintControl(KDCControl, VisitechControl, LoadcellControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=False, top_level=False):
        if self.state == "uninitialized":
            super().initialize(run_in_thread=False, top_level=False)
            if top_level and self.all_hardware_connected:
                log.info("Printer initialized, all hardware ready.")

    def post_print_tasks(self):
        """Move BP stage up 'Distance up (mm)'' then to top"""
        super().post_print_tasks()
        defaults_layer_settings = self.print_settings.get("Default layer settings")
        default_position_settings = defaults_layer_settings.get("Position settings")

        self.move_build_platform_up(default_position_settings)
        self.bp_stage.goToBPmax()
        time.sleep(1.0)

class HR4_PrintControl(VisitechControl, KeyenceControl, LoadcellControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=False, top_level=False):
        if self.state == "uninitialized":
            super().initialize(run_in_thread=False, top_level=False)
            if top_level and self.all_hardware_connected:
                log.info("Printer initialized, all hardware ready.")

    def __init__(self):
        super().__init__()
        self.coord_systems = config_dict["galil"]["coord_systems"]
        self.default_position_settings = None
        self.default_x_offset = None
        self.default_y_offset = None

    def get_focus(self):
        """Return 'Focus' axis position in um"""
        return int(
            self.focus_stage.getFocusPosition() * 1000
        )

    def galil_finalize_setup_thread(self):
        x_pos = self.coord_systems["visitech"]["X"]
        y_pos = self.coord_systems["visitech"]["Y"]
        focus_pos = self.coord_systems["visitech"]["Focus"]
        bp_pos = self.bp_stage.top_position
        xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False)
        focus_thread = self.focus_stage.threadedFocusMove(log, focus_pos, join=False)
        bp_thread = self.focus_stage.threadedBPMove(log, bp_pos, join=False)
        for thread in xy_threads:
            if thread is not None:
                thread.join()
        if focus_thread is not None:
            focus_thread.join()
        if bp_thread is not None:
            bp_thread.join()

    def post_print_tasks(self):
        """Move all galil stages to their starting positions"""
        super().post_print_tasks()

        self.move_build_platform_up(self.default_position_settings)

        x_pos = self.coord_systems["visitech"]["X"]
        y_pos = self.coord_systems["visitech"]["Y"]
        focus_pos = self.coord_systems["visitech"]["Focus"]
        bp_pos = self.bp_stage.top_position
        xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False, speed_x=None, speed_y=None, acceleration_x=None, acceleration_y=None)
        focus_thread = self.focus_stage.threadedFocusMove(log, focus_pos, join=False, speed=None, acceleration=None)
        bp_thread = self.focus_stage.threadedBPMove(log, bp_pos, join=False, speed=None, acceleration=None)
        for thread in xy_threads:
            if thread is not None:
                thread.join()
        if focus_thread is not None:
            focus_thread.join()
        if bp_thread is not None:
            bp_thread.join()

class MR1v1_PrintControl(HR4_PrintControl, WintechControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=False, top_level=False):
        if self.state == "uninitialized":
            super().initialize(run_in_thread=False, top_level=False)
            if top_level and self.all_hardware_connected:
                log.info("Printer initialized, all hardware ready.")

    def __init__(self):
        super().__init__()
        self.default_light_engine = None
        self.coord_systems = config_dict["galil"]["coord_systems"]

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

    def pre_print_tasks(self):
    # Move focus around a little bit before print. Seems to help repeatablility
        for light_engine in config_dict["screen"]["light_engines"]:
            self.focus_stage.absMoveFocus(self.coord_systems[f"keyence_{light_engine}"]["Focus"])
            time.sleep(1.0)
        super().pre_print_tasks()


class HR3v3_PrintControl(HR3v3u_PrintControl, FilmGPIOControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=False, top_level=False):
        if self.state == "uninitialized":
            super().initialize(run_in_thread=False, top_level=False)
            if top_level and self.all_hardware_connected:
                log.info("Printer initialized, all hardware ready.")


class HR4Film_PrintControl(HR4_PrintControl, FilmGPIOControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=False, top_level=False):
        if self.state == "uninitialized":
            super().initialize(run_in_thread=False, top_level=False)
            if top_level and self.all_hardware_connected:
                log.info("Printer initialized, all hardware ready.")