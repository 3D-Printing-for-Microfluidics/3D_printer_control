# -*- coding: utf-8 -*-
"""Dummy Solus module, used for development."""
import time


class Solus:
    def __init__(self, serialNum):
        self.serialNum = serialNum
    #     self.is_open = False
    #     self.initialized = False
    #     self.z = 'up'

    def connect(self):
        pass

    def initialize(self):
        time.sleep(3)

    def goToZmin(self):
        time.sleep(3)

    def goToZmax(self):
        time.sleep(3)
        
    def goToFirstLayerHeight(self, *args):
        time.sleep(3)
        
    def resume(self, *args):
        pass
        
    def printCycle(self, *args):
        pass
        
    def pause(self):
        pass
        
    def __del__(self):
        pass
