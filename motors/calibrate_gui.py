from tkinter import Tk, Label, Button, Entry, IntVar, END, W, E

class Calibrate:

    def __init__(self, master):
        self.master = master
        master.title("Focus Calibration")

        self.tip = 0
        self.tilt = 0
        self.distance = 0

        self.buttons = []
        self.labels = []
        self.labels_dynamic = []
        self.labels_dynamic_text = []
        self.measurements = [0,0,0]

        # Specify Buttons
        self.axes = ["Tip","Tilt","Distance"]
        self.button_text = ["-100","-10","-1","+1","+10","+100"]
        self.button_value = [-100,  -10,  -1,   1,   10,   100]


        for i in self.button_value:
            print(i)

        # Create and add buttons and labels
        for a in range(len(self.axes)):
            # add first column labels
            self.labels.append(Label(master, text=self.axes[a]))
            self.labels[a].grid(row=a, column=0, sticky=W)

            # add second column dynamic labels
            self.labels_dynamic_text.append(IntVar())
            self.labels_dynamic_text[a].set(self.measurements[a])
            self.labels_dynamic.append(Label(master, textvariable=self.labels_dynamic_text[a]))
            self.labels_dynamic[a].grid(row=a, column=1)

            # add increment/decrement buttons
            for i in range(len(self.button_text)):
                print("button",a,i)
                self.buttons.append(Button(master, text=self.button_text[i], command=lambda: self.update(a,i)))
                self.buttons[len(self.button_text)*a+i].grid(column=i+2, row=a)

    ## TODO: Use partial function to keep arguments dynamic
    def update(self, row, column):
        print("update:",row,column)
        self.measurements[row] += self.button_value[column]
        print(self.button_value[column])
        self.labels_dynamic_text[row].set(self.measurements[row])

        for a in range(len(self.axes)):
            self.labels_dynamic_text[a].set(self.measurements[a])

root = Tk()
my_gui = Calibrate(root)
root.mainloop()

# # Create entry box
# vcmd = master.register(self.validate) # we have to wrap the command
# self.entry = Entry(master, validate="key", validatecommand=(vcmd, '%P'))
# # layout
# self.entry.grid(row=1, column=0, columnspan=3, sticky=W+E)
# # put this in update
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