import RPi.GPIO as GPIO
import time
from .calibrationStage import CalibrationStage

class Stepper_28BYJ48(CalibrationStage):

    def __init__(self, pinNumbers):
        # Motor parameters 
        self.spr = 4096     # From spec sheet we know that the motors have 4096 steps per revolution
        self.dpr = 381      # We also know distance per revolution to be 381 um
        self.delay = .003   # Min delay for 28BYJ-48 is 2 ms, we will set it at 4ms

        # GPIO pins used for each motor 
        self.pin_names = ['IN1','IN2','IN3','IN4']
        self.pins = {
            self.pin_names[0]:pinNumbers[0],
            self.pin_names[1]:pinNumbers[1],
            self.pin_names[2]:pinNumbers[2],
            self.pin_names[3]:pinNumbers[3]
        }

        self.drivePattern = [[1, 1, 0, 0],
                             [0, 1, 1, 0],
                             [0, 0, 1, 1]]

    def initialize(self):
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)   
        GPIO.setwarnings(False) # running GPIO.cleanup() for some reason leaves some pins on, even after turning them off. 
                                # Without it, you always get a warning that pins are in use, so I'm disabling warnings here. 
        for pin in self.pins: 
            GPIO.setup(self.pins[pin], GPIO.OUT) # set every pin as output    

    # Set GPIO pins on specified motor to given pattern 
    def setStep(self, pinPattern):
        for i, pattern in enumerate(pinPattern):
            GPIO.output(self.pins[self.pin_names[i]], pattern)

    def move(self, steps):
        if steps > 0:    # forward motion 
            for _ in range(0, steps):
                self.setStep([1, 0, 0, 1])
                time.sleep(self.delay)
                self.setStep([1, 1, 0, 0])
                time.sleep(self.delay)
                self.setStep([0, 1, 1, 0])
                time.sleep(self.delay)
                self.setStep([0, 0, 1, 1])
                time.sleep(self.delay)
        else:           # backward motion 
            for _ in range(0, abs(steps)):
                self.setStep([1, 0, 0, 1])
                time.sleep(self.delay)
                self.setStep([0, 0, 1, 1])
                time.sleep(self.delay)
                self.setStep([0, 1, 1, 0])
                time.sleep(self.delay)
                self.setStep([1, 1, 0, 0])
                time.sleep(self.delay)
        # This turns off current to the coils so the motor does not get hot
        self.setStep([0, 0, 0, 0]) 

    # Iteratively toggle each input to each motor. 
    # You should be able to watch the LEDs flash in this order: A, B, C, D, C, B, A, off   
    # If they go in some other order or don't light at all, the board has been wired incorrectly 
    def test_sequence(self):
        delay = .1
        self.setStep([1,0,0,0])
        time.sleep(delay)
        self.setStep([0,1,0,0])
        time.sleep(delay)
        self.setStep([0,0,1,0])
        time.sleep(delay)
        self.setStep([0,0,0,1])
        time.sleep(delay)
        self.setStep([0,0,1,0])
        time.sleep(delay)
        self.setStep([0,1,0,0])
        time.sleep(delay)
        self.setStep([1,0,0,0])
        time.sleep(delay)
        self.setStep([0,0,0,0])
        time.sleep(delay)

    def home(self):
        pass

    def setAbsolute(self):
        pass

    def setRelative(self):
        pass

    def getCurrentPos(self):
        return "none"

    def __del__(self):
        try: 
            # always turn off the motor
            self.setStep([0,0,0,0])
        except:
            pass

if __name__ == '__main__':
    # NOTE: the pin numbers are the GPIO pin values, not the pin numbers
    c = Stepper_28BYJ48([14, 15, 18, 4])
    c.test_sequence()