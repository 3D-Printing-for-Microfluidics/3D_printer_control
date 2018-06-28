# -*- coding: utf-8 -*-
"""Dummy I2C module."""


class LightEngineI2C: 

    ledPower = 100

    def connect(self):
        pass

    def start(self):
        pass
        
    def stop(self):
        pass
        
    def setLedAmplitude(self, i):
        pass
        
    def parseSendSequence(self, sequence, repeat):
        pass
        
    def disconnectServer(self):
        pass