import time

class Stepper_28BYJ48:
    def __init__(self, pins):
        print("28byj48: init(", pins, ")")
    
    def move(self, steps):
        print("28byj48: move(", steps, ")")

    def initialize(self):
        print("28byj48: initialize()")

    def home(self):
        pass

    def getCurrentPos(self):
        pass

    def setRelative(self):
        pass

    def setAbsolute(self):
        pass