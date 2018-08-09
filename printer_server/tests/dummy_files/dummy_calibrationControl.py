# -*- coding: utf-8 -*-
"""Dummy CalibrationControl module, used for development."""
import time


class CalibrationControl:

    def setStep(self, motor, pinPattern):
        print("CalibrationControl: setStep(" + motor + "," + pinPattern + ")")

    def move(self, motor, steps): 
        print("CalibrationControl: move(" + motor + "," + steps + ")")
        time.sleep(1)
    
    def test_sequence(self):
        print("CalibrationControl: test_sequence()")
        time.sleep(1)
