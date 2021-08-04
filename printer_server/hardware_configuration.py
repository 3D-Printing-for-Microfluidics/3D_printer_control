import logging
from printer_server.drivers.screen import ScreenThread
from printer_server.drivers.galil import Galil, Galil_dummy
from printer_server.drivers.visitech import Visitech, Visitech_dummy
from printer_server.drivers.kdc101 import KDC101, KDC101_dummy
from printer_server.drivers.tiptilt import TipTilt, TipTilt_dummy
from printer_server.drivers.loadcell import LoadCell, Loadcell_dummy

default_log_level = logging.INFO
dummy = False

# hr3v3
griffin_calibration_position = 108800
griffin_bottom_position = 368000

loadcell_hwid = "PID=16C0:0483 SER=5712360"
loadcell_calibration_intercept = 34932.0
loadcell_calibration_slope = -1.79

tiptilt_hwid = "PID=16C0:0483 SER=5800580"


class Printer3D:
    def __init__(self):
        self.screen = ScreenThread(log_level=default_log_level)
        if dummy:
            self.galil = Galil_dummy()
            self.visitech = Visitech_dummy()
            self.kdc = KDC101_dummy()
            self.tiptilt = TipTilt_dummy(verbose=True)
            self.loadcell = Loadcell_dummy()
        else:
            self.galil = Galil(
                log_level=default_log_level,
                bottom_position=griffin_bottom_position,
                calibration_position=griffin_calibration_position,
            )
            self.visitech = Visitech(log_level=default_log_level)
            self.kdc = KDC101(log_level=default_log_level)
            self.tiptilt = TipTilt(hwid=tiptilt_hwid, log_level=default_log_level)
            self.loadcell = LoadCell(
                hwid=loadcell_hwid,
                log_level=default_log_level,
                intercept=loadcell_calibration_intercept,
                slope=loadcell_calibration_slope,
            )


driver_handles = Printer3D()
