# -*- coding: utf-8 -*-
"""Hardware module. It integrates the Galil controller and Projector into a Printer3D."""
from printer_server.printer.galil import Galil
from printer_server.printer.projector import Projector
from printer_server.printer.print_settings import PrintSettings
# from printer_server.printer.calibrationControl import CalibrationControl


projectorResolution = (2560, 1600)


class Printer3D:
    state = 'uninitialized'
    galil = Galil()
    projector = Projector(projectorResolution)

    def init_app(self, app):
        # self.projector.i2c.logger = app.logger
        pass

printer3d = Printer3D()
# calibrationControl = CalibrationControl()
