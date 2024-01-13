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

class HR4_PrintControl(VisitechControl, KeyenceControl, LoadcellControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=False, top_level=False):
        if self.state == "uninitialized":
            super().initialize(run_in_thread=False, top_level=False)
            if top_level and self.all_hardware_connected:
                log.info("Printer initialized, all hardware ready.")

class MR1v1_PrintControl(HR4_PrintControl, WintechControl):
    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=False, top_level=False):
        if self.state == "uninitialized":
            super().initialize(run_in_thread=False, top_level=False)
            if top_level and self.all_hardware_connected:
                log.info("Printer initialized, all hardware ready.")


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