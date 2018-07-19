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

        # Create labels 
        # self.tip_label = Label(master, text="Tip:")
        # self.tilt_label = Label(master, text="Tilt:")
        # self.distance_label = Label(master, text="Distance:")

        # Create auto updating labels
        self.tip_label_text = IntVar()
        self.tip_label_text.set(self.tip)
        self.tip_label_reading = Label(master, textvariable=self.tip_label_text)

        self.tilt_label_text = IntVar()
        self.tilt_label_text.set(self.tilt)
        self.tilt_label_reading = Label(master, textvariable=self.tilt_label_text)

        self.distance_label_text = IntVar()
        self.distance_label_text.set(self.distance)
        self.distance_label_reading = Label(master, textvariable=self.distance_label_text)

        # # Create entry box 
        # vcmd = master.register(self.validate) # we have to wrap the command
        # self.entry = Entry(master, validate="key", validatecommand=(vcmd, '%P'))
        # # layout 
        # self.entry.grid(row=1, column=0, columnspan=3, sticky=W+E)
        # # put this in update 
        # self.entry.delete(0, END)

        # Create buttons 
        axes = ["Tip","Tilt","Distance"]
        button_text = ["-100","-10","-1","0","+1","+10","+100"]

        for a in range(len(axes)):    
            self.labels.append(Label(master, text=axes[a]))
            self.labels[a].grid(row=a, column=0, sticky=W)

            # self.labels_dynamic_text[a] = IntVar()
            # self.labels_dynamic_text[a].set(self.measurements[a])
            # self.labels_dynamic[a] = Label(master, textvariable=self.labels_dynamic_text[a])

            for i in range(len(button_text)):
                self.buttons.append(Button(master, text=button_text[i], command=lambda: self.update2(a,i)))
                self.buttons[len(button_text)*a+i].grid(column=i+2, row=a)
                print("add: ",a,i)

        # self.add_1_tip_button = Button(master, text=plus_one_text, command=lambda: self.update("add_1_tip"))
        # self.add_1_tilt_button = Button(master, text=plus_one_text, command=lambda: self.update("add_1_tilt"))
        # self.add_1_distance_button = Button(master, text=plus_one_text, command=lambda: self.update("add_1_distance"))
        
        # self.sub_1_tip_button = Button(master, text=minus_one_text, command=lambda: self.update("sub_1_tip"))
        # self.sub_1_tilt_button = Button(master, text=minus_one_text, command=lambda: self.update("sub_1_tilt"))
        # self.sub_1_distance_button = Button(master, text=minus_one_text, command=lambda: self.update("sub_1_distance"))

        # Layout 
        tip_row = 0
        tilt_row = 1
        distance_row = 2

        label_col = 0
        label_align = W
        measure_col = 1
        # sub_10_col = 2
        sub_1_col = 3
        add_1_col = 4
        # add_10_col = 5


        # put position labels in column 1
        self.tip_label_reading.grid(row=tip_row, column=measure_col)
        self.tilt_label_reading.grid(row=tilt_row, column=measure_col)
        self.distance_label_reading.grid(row=distance_row, column=measure_col)

        


    def validate(self, new_text):
        if not new_text: # the field is being cleared
            self.entered_number = 0
            return True

        try:
            self.entered_number = int(new_text)
            return True
        except ValueError:
            return False


    def update2(self, method, a):
        print("yay")

    def update(self, method):
        if   method == "add_1_tip":
            self.tip += 1
        elif method == "sub_1_tip":
            self.tip -= 1
        elif method == "add_1_tilt":
            self.tilt += 1
        elif method == "sub_1_tilt":
            self.tilt -= 1
        elif method == "add_1_distance":
            self.distance += 1
        elif method == "sub_1_distance":
            self.distance -= 1
        else: # reset
            print("weird")


        self.tip_label_text.set(self.tip)
        self.tilt_label_text.set(self.tilt)
        self.distance_label_text.set(self.distance)

root = Tk()
my_gui = Calibrate(root)
root.mainloop()