import RPi.GPIO as GPIO
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
                self.pin_names[0]:14,    
                self.pin_names[1]:15,   
                self.pin_names[2]:18,   
                self.pin_names[3]:4    
            },
            self.motors[1]:{            # tilt 
                self.pin_names[0]:17,   
                self.pin_names[1]:27,    
                self.pin_names[2]:22,  
                self.pin_names[3]:23    
            },
            self.motors[2]:{            # distance 
                self.pin_names[0]:24,    
                self.pin_names[1]:25,     
                self.pin_names[2]:10,    
                self.pin_names[3]:9    
            }
        }
        
    def initialize(self):
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)   
        GPIO.setwarnings(False) # running GPIO.cleanup() for some reason leaves some pins on, even after turning them off. 
                                # Without it, you always get a warning that pins are in use, so I'm disabling warnings here. 
        for motor in self.pins:   
            for pin in self.pins[motor]: 
                GPIO.setup(self.pins[motor][pin], GPIO.OUT) # set every pin as output      

    # Set GPIO pins on specified motor to given pattern 
    def setStep(self, motor, pinPattern):
        for i in range(len(self.pin_names)):
            GPIO.output(self.pins[motor][self.pin_names[i]], pinPattern[i])

    # Move the specified motor by specified steps 
    def move(self, motor, steps): 
        if steps > 0:    # forward motion 
            for _ in range(0, steps):
                self.setStep(motor, [1, 0, 0, 1])
                time.sleep(self.delay)
                self.setStep(motor, [1, 1, 0, 0])
                time.sleep(self.delay)
                self.setStep(motor, [0, 1, 1, 0])
                time.sleep(self.delay)
                self.setStep(motor, [0, 0, 1, 1])
                time.sleep(self.delay)
        else:           # backward motion 
            for _ in range(0, abs(steps)):
                self.setStep(motor, [1, 0, 0, 1])
                time.sleep(self.delay)
                self.setStep(motor, [0, 0, 1, 1])
                time.sleep(self.delay)
                self.setStep(motor, [0, 1, 1, 0])
                time.sleep(self.delay)
                self.setStep(motor, [1, 1, 0, 0])
                time.sleep(self.delay)
        # This turns off current to the coils so the motor does not get hot
        self.setStep(motor, [0, 0, 0, 0]) 

    # Iteratively toggle each input to each motor. 
    # You should be able to watch the LEDs flash in this order: A, B, C, D, C, B, A, off   
    # If they go in some other order or don't light at all, the board has been wired incorrectly 
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

if __name__ == '__main__':
    c=CalibrationControl()
    c.test_sequence()
