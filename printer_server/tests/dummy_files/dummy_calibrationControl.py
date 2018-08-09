# -*- coding: utf-8 -*-
"""Dummy CalibrationMotor module, used for development."""
import time

class CalibrationControl:

    def __init__(self):

        # Button parameters 
        self.motors = ["Tip","Tilt","Distance"] # if you add a motor here, make sure to add it's pins below 

        # Motor parameters 
        self.spr = 4096     # From spec sheet we know that the motors have 4096 steps per revolution
        self.dpr = 381      # We also know distance per revolution to be 381 um
        self.delay = .003   # Min delay for 28BYJ-48 is 2 ms, we will set it at 4ms

        # GPIO pins used for each motor 
        self.pin_names = ['IN1','IN2','IN3','IN4']
        self.pins = {
            self.motors[0]:{            # tip 
                self.pin_names[0]:23,    
                self.pin_names[1]:24,   
                self.pin_names[2]:22,   
                self.pin_names[3]:10    
            },
            self.motors[1]:{            # tilt 
                self.pin_names[0]:15,   
                self.pin_names[1]:18,    
                self.pin_names[2]:17,  
                self.pin_names[3]:27    
            },
            self.motors[2]:{            # distance 
                self.pin_names[0]:4,    
                self.pin_names[1]:3,     
                self.pin_names[2]:2,    
                self.pin_names[3]:14    
            }
        }

    def setStep(self, motor, pinPattern):
        time.sleep(1)

    def move(self, motor, steps): 
        time.sleep(1)
    
    def test_sequence(self):
        delay = .1
        for m in self.motors:
            self.setStep(m, [1,0,0,0])
            time.sleep(delay)
            self.setStep(m, [0,1,0,0])
            time.sleep(delay)
            self.setStep(m, [0,0,1,0])
            time.sleep(delay)
            self.setStep(m, [0,0,0,1])
            time.sleep(delay)
            self.setStep(m, [0,0,1,0])
            time.sleep(delay)
            self.setStep(m, [0,1,0,0])
            time.sleep(delay)
            self.setStep(m, [1,0,0,0])
            time.sleep(delay)
            self.setStep(m, [0,0,0,0])
            time.sleep(delay)

    def __del__(self):
        try: 
            # always turn off all motor controls 
            for m in self.motors: 
                self.setStep(m, [0,0,0,0])
        except:
            pass