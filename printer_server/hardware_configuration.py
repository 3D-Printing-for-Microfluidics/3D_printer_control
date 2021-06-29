import logging
from printer_server.drivers.screen import ScreenThread
from printer_server.drivers.galil import Galil, Galil_dummy
from printer_server.drivers.visitech import Visitech, Visitech_dummy
from printer_server.drivers.kdc101 import KDC101, KDC101_dummy
from printer_server.drivers.tiptilt import TipTilt, TipTilt_dummy
from printer_server.drivers.loadcell import LoadCell, Loadcell_dummy

default_log_level = logging.INFO
dummy = False


class Printer3D:
    def __init__(self):
        self.screen = ScreenThread(log_level=default_log_level)
        print(self.screen)
        if dummy:
            self.galil = Galil_dummy()
            self.visitech = Visitech_dummy()
            self.kdc = KDC101_dummy()
            self.tiptilt = TipTilt_dummy(verbose=True)
            self.loadcell = Loadcell_dummy()
        else:
            self.galil = Galil(log_level=default_log_level)
            self.visitech = Visitech(log_level=default_log_level)
            self.kdc = KDC101(log_level=default_log_level)
            self.tiptilt = TipTilt(log_level=default_log_level)
            self.loadcell = LoadCell(log_level=default_log_level)


driver_handles = Printer3D()
