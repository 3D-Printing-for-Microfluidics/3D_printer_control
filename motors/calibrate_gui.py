from tkinter import Tk, Label, Button, Entry, IntVar, END, W, E
from functools import partial

class Calibrate:

    def __init__(self, master):
        self.master = master
        master.title("Focus Calibration")
        self.buttons = []
        self.labels = []
        self.measurements = []
        self.labels_dynamic = []
        self.labels_dynamic_text = []

        # Specify Buttons
        self.axes = ["Tip","Tilt","Distance"]
        self.button_text = ["-1000","-100","-10","-1","+1","+10","+100", "+1000"]

        # Create and add buttons and labels
        for a in range(len(self.axes)):
            # add a spot in the measurement array to hold the current value
            self.measurements.append(0)

            # add first column labels
            self.labels.append(Label(master, text=self.axes[a]))
            self.labels[a].grid(row=a, column=0, sticky=W)

            # add second column dynamic labels
            self.labels_dynamic_text.append(IntVar())
            self.labels_dynamic_text[a].set(self.measurements[a])
            self.labels_dynamic.append(Label(master, textvariable=self.labels_dynamic_text[a]))
            self.labels_dynamic[a].grid(row=a, column=1)

            # add buttons
            for i in range(len(self.button_text)):
                button_press_func = partial(self.update_labels, a, i)
                self.buttons.append(Button(master, text=self.button_text[i], command=button_press_func))
                self.buttons[len(self.button_text)*a+i].grid(column=i+2, row=a)

    # update the dynamic labels when a button is pressed 
    def update_labels(self, row, column):
        self.measurements[row] += int(float(self.button_text[column]))  # convert button text to int and add/subtract
        self.labels_dynamic_text[row].set(self.measurements[row])       # update the associated dynamic label 

root = Tk()
my_gui = Calibrate(root)
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