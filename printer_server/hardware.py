# -*- coding: utf-8 -*-
"""Hardware module. It integrates the hardware modules into a Printer3D."""
from printer_server.hardware_drivers.galil import Galil, Galil_dummy
from printer_server.hardware_drivers.projector import Projector, Projector_dummy
from printer_server.hardware_drivers.kdc101 import KDC101, KDC101_dummy
from printer_server.hardware_drivers.tiptilt import TipTilt, TipTilt_dummy
from printer_server.hardware_drivers.print_settings import PrintSettings

projectorResolution = (2560, 1600)

class Printer3D:
    def __init__(self, dummy=False):
        self.dummy = dummy

        if self.dummy:
            self.state = 'uninitialized'
            self.galil = Galil_dummy()
            self.projector = Projector_dummy(projectorResolution)
            self.kdc = KDC101_dummy()
            self.tiptilt = TipTilt_dummy(verbose=True)
        else:
            self.state = 'uninitialized'
            self.galil = Galil(verbose=True)
            self.projector = Projector(projectorResolution)
            self.kdc = KDC101()
            self.tiptilt = TipTilt(verbose=True)

printer3d = Printer3D(dummy=False)
