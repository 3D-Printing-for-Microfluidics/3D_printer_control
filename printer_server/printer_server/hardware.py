# -*- coding: utf-8 -*-
"""Hardware module. It integrates the hardware modules into a Printer3D."""
from printer_server.printer.galil import Galil
from printer_server.printer.projector import Projector
from printer_server.printer.kdc101 import KDC101
from printer_server.printer.tiptilt import TipTilt
from printer_server.printer.print_settings import PrintSettings

projectorResolution = (2560, 1600)

class Printer3D:
    state = 'uninitialized'
    galil = Galil()
    projector = Projector(projectorResolution)
    kdc = KDC101()
    tiptilt = TipTilt(verbose=True)

printer3d = Printer3D()
