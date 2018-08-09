# -*- coding: utf-8 -*-
"""Dummy I2C module"""


class LightEngineI2C: 

    ledPower = 100

    def connect(self):
        print("LightEngineI2C: connect()")

    def start(self):
        print("LightEngineI2C: start()")
        
    def stop(self):
        print("LightEngineI2C: stop()")
        
    def setLedAmplitude(self, i):
        print("LightEngineI2C: setLedAmplitude(" + i + ")")
        
    def parseSendSequence(self, sequence, repeat):
        print("LightEngineI2C: parseSendSequence(", sequence, ",", repeat, ")")
        
    def disconnectServer(self):
        print("LightEngineI2C: disconnectServer()")