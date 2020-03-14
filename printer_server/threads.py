# -*- coding: utf-8 -*-
"""Thread module"""
from printer_server.printing_threads import PrintingThreads
from printer_server.calibration_threads import manualControls

printingThreads = PrintingThreads()
manualControls = ManualControls()
