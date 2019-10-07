# -*- coding: utf-8 -*-
"""Dummy hardware module"""
from printer_server.printer.galil import Galil
from printer_server.printer.projector import Projector
from printer_server.printer.print_settings import PrintSettings


projectorResolution = (640, 400)


class Printer3D:
    state = 'uninitialized'
    galil = Galil()
    projector = Projector(projectorResolution, fullscreen=False)

    def init_app(self, app):
        self.projector.i2c.logger = app.logger


printer3d = Printer3D()
