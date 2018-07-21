from tkinter import Tk, Label, Button, Entry, IntVar, END, W, E
from functools import partial
import RPi.GPIO as GPIO
import time

class CalibrationControl:

    def __init__(self, master):

        # GUI containers  
        self.master = master
        master.title("Focus Calibration")
        self.buttons = []
        self.labels = []
        self.measurements = []
        self.labels_dynamic = []
        self.labels_dynamic_text = []

        # Button parameters 
        self.motors = ["Tip","Tilt","Distance"] # if you add a motor here, make sure to add it's pins below 
        self.button_text = ["-100","-10","-1","+1","+10","+100"]

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

        # Create and add buttons and labels to GUI
        Label(master, text="Motor").grid(row=0, column=0)
        Label(master, text="Location").grid(row=0, column=1)
        Label(master, text="Move").grid(row=0, column=2, columnspan=len(self.button_text))
        
        for m in range(len(self.motors)):   # for each motor 
            # add m spot in the measurement array to hold the current value
            self.measurements.append(0)

            # add first column labels
            self.labels.append(Label(master, text=self.motors[m]))
            self.labels[m].grid(row=m+1, column=0, sticky=E)

            # add second column dynamic labels
            self.labels_dynamic_text.append(IntVar())
            self.labels_dynamic_text[m].set(self.measurements[m])
            self.labels_dynamic.append(Label(master, textvariable=self.labels_dynamic_text[m]))
            self.labels_dynamic[m].grid(row=m+1, column=1)

            # add buttons
            for i in range(len(self.button_text)):
                button_press_func = partial(self.update_labels, m, i)
                self.buttons.append(Button(master, text=self.button_text[i], command=button_press_func))
                self.buttons[len(self.button_text)*m+i].grid(column=i+2, row=m+1)

        test_button = Button(master, text="Run test sequence", command=self.test_sequence)
        test_button.grid(column=len(self.button_text)-1, row=len(self.motors)+1, columnspan=3)

        # Setup GPIO
        GPIO.setmode(GPIO.BCM)   
        for motor in self.pins:   
            for pin in self.pins[motor]: 
                GPIO.setup(self.pins[motor][pin], GPIO.OUT) # set every pin as output      

    # Set GPIO pins on specified motor to given pattern 
    def setStep(self, motor, pinPattern):
        for i in range(len(self.pin_names)):
            GPIO.output(self.pins[motor][self.pin_names[i]], pinPattern[i])

    # Move the specified motor by specified steps 
    def move(self, delay, motor, steps): 
        if steps > 0:    # forward motion 
            for _ in range(0, steps):
                self.setStep(motor, [1, 0, 0, 1])
                time.sleep(delay)
                self.setStep(motor, [1, 1, 0, 0])
                time.sleep(delay)
                self.setStep(motor, [0, 1, 1, 0])
                time.sleep(delay)
                self.setStep(motor, [0, 0, 1, 1])
                time.sleep(delay)
        else:           # backward motion 
            for _ in range(0, abs(steps)):
                self.setStep(motor, [1, 0, 0, 1])
                time.sleep(delay)
                self.setStep(motor, [0, 0, 1, 1])
                time.sleep(delay)
                self.setStep(motor, [0, 1, 1, 0])
                time.sleep(delay)
                self.setStep(motor, [1, 1, 0, 0])
                time.sleep(delay)
        # This turns off current to the coils so the motor does not get hot
        self.setStep(motor, [0, 0, 0, 0]) 

    def __del__(self):
        try: 
            GPIO.cleanup()  # always close GPIO pins when done 
        except:
            pass

    # Move motors and update dynamic labels. Called on button clicks   
    def update_labels(self, motor, value):
        valueInt = int(float(self.button_text[value]))                  # convert button text to int 
        self.measurements[motor] += valueInt                            # add/subtract 
        self.move(self.delay, self.motors[motor], valueInt)             # move motor 
        self.labels_dynamic_text[motor].set(self.measurements[motor])   # update the associated dynamic label 

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
    
if __name__ == '__main__':
    try:
        root = Tk()
        controller = CalibrationControl(root)
        root.mainloop()
    except:
        GPIO.cleanup()
