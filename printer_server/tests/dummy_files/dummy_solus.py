# -*- coding: utf-8 -*-
"""Dummy Solus module, used for development."""
import time


class Solus:
    def __init__(self, hwid):
        self.hwid = hwid

    def connect(self):
        print("Solus: connect()")        

    def initialize(self):
        print("Solus: initialize()")
        time.sleep(1)

    def goToZmin(self):
        print("Solus: goToZmin()")
        time.sleep(1)

    def goToZmax(self):
        print("Solus: goToZmax()")
        time.sleep(1)
        
    def goToFirstLayerHeight(self, *args):
        print("Solus: goToFirstLayerHeight()")
        time.sleep(1)
        
    def resume(self, *args):
        print("Solus: resume()")
        
    def printCycle(self, *args):
        print("Solus: printCycle()")
        
    def pause(self):
        print("Solus: pause()")
        
    def __del__(self):
        pass
