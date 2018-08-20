# -*- coding: utf-8 -*-
"""Dummy hardware module"""
from printer_server.printer.solus import Solus
from printer_server.printer.projector import Projector
from printer_server.printer.print_settings import PrintSettings
from printer_server.printer.calibrationControl import CalibrationControl


solusHWID = '1A86:7523'  # specific to each arduino 
projectorResolution = (640, 400)


class Printer3D:
    state = 'uninitialized'
    solus = Solus(hwid=solusHWID)
    projector = Projector(projectorResolution, fullscreen=False)

    def init_app(self, app):
        self.projector.i2c.logger = app.logger


printer3d = Printer3D()
calibrationControl = CalibrationControl()

