# -*- coding: utf-8 -*-
"""Hardware module. It integrates Solus and Projector into a Printer3D."""
from printer_server.printer.solus import Solus
from printer_server.printer.projector import Projector
from printer_server.printer.print_settings import PrintSettings


solusHWID = '1A86:7523'  # specific to each arduino 
projectorResolution = (2560, 1600)


class Printer3D:
    state = 'uninitialized'
    solus = Solus(hwid=solusHWID)
    projector = Projector(projectorResolution)

    def init_app(self, app):
        self.projector.i2c.logger = app.logger


printer3d = Printer3D()

