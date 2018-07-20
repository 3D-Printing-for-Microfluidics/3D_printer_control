from tkinter import Tk, Label, Button, Entry, IntVar, END, W, E
from functools import partial
import RPi.GPIO as GPIO
import time

class CalibrateControl:

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
        self.motors = ["Tip","Tilt","Distance"]
        self.button_text = ["-1000","-100","-10","-1","+1","+10","+100", "+1000"]

        # Motor parameters 
        self.spr = 4096     # From spec sheet we know that the motors have 4096 steps per revolution
        self.dpr = 381      # We also know distance per revolution to be 381 um
        self.delay = .004   # Min delay for 28BYJ-48 is 2 ms, we will set it at 4ms

        # GPIO pins used for each motor 
        self.pin_names = ['A1','A2','B1','B2']
        self.pins = {
            self.motors[0]:{              # tip 
                self.pin_names[0]:1,    #  A1 
                self.pin_names[1]:7,    #  A2 
                self.pin_names[2]:8,    #  B1
                self.pin_names[3]:25    #  B2 
            },
            self.motors[1]:{              # tilt 
                self.pin_names[0]:2,    #  A1 
                self.pin_names[1]:3,    #  A2 
                self.pin_names[2]:4,    #  B1
                self.pin_names[3]:5     #  B2 
            },
            self.motors[2]:{              # distance 
                self.pin_names[0]:6,    #  A1 
                self.pin_names[1]:9,    #  A2 
                self.pin_names[2]:10,   #  B1
                self.pin_names[3]:11    #  B2 
            }
        }

        # Create and add buttons and labels to GUI
        for m in range(len(self.motors)):
            # add m spot in the measurement array to hold the current value
            self.measurements.append(0)

            # add first column labels
            self.labels.append(Label(master, text=self.motors[m]))
            self.labels[m].grid(row=m, column=0, sticky=W)

            # add second column dynamic labels
            self.labels_dynamic_text.append(IntVar())
            self.labels_dynamic_text[m].set(self.measurements[m])
            self.labels_dynamic.append(Label(master, textvariable=self.labels_dynamic_text[m]))
            self.labels_dynamic[m].grid(row=m, column=1)

            # add buttons
            for i in range(len(self.button_text)):
                button_press_func = partial(self.update_labels, m, i)
                self.buttons.append(Button(master, text=self.button_text[i], command=button_press_func))
                self.buttons[len(self.button_text)*m+i].grid(column=i+2, row=m)

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

    # Move motors and update dynamic labels. Called on button clicks   
    def update_labels(self, motor, value):
        valueInt = int(float(self.button_text[value]))                  # convert button text to int 
        self.measurements[motor] += valueInt                            # add/subtract 
        print("move(",self.delay, self.pin_names[motor], valueInt,")")
        self.move(self.delay, self.motors[motor], valueInt)             # move motor 
        self.labels_dynamic_text[motor].set(self.measurements[motor])   # update the associated dynamic label 

root = Tk()
my_gui = CalibrateControl(root)
root.mainloop()

# # This code can optionally be used to create an entry box
# vcmd = master.register(self.validate) # we have to wrap the command
# self.entry = Entry(master, validate="key", validatecommand=(vcmd, '%P'))
# # layout
# self.entry.grid(row=1, column=0, columnspan=3, sticky=W+E)
# # put this in the update function (clears the text box)
# self.entry.delete(0, END)

# def validate(self, new_text):
#     if not new_text: # the field is being cleared
#         self.entered_number = 0
#         return True

#     try:
#         self.entered_number = int(new_text)
#         return True
#     except ValueError:
#         return False