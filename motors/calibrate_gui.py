from tkinter import Tk, Label, Button, Entry, IntVar, END, W, E

class Calibrate:

    def __init__(self, master):
        self.master = master
        master.title("Focus Calibration")

        self.tip = 0
        self.tilt = 0
        self.distance = 0
        
        self.buttons = []

        # Create labels 
        self.tip_label = Label(master, text="Tip:")
        self.tilt_label = Label(master, text="Tilt:")
        self.distance_label = Label(master, text="Distance:")

        # Create updating labels
        self.tip_label_text = IntVar()
        self.tip_label_text.set(self.tip)
        self.tip_label_reading = Label(master, textvariable=self.tip_label_text)

        self.tilt_label_text = IntVar()
        self.tilt_label_text.set(self.tilt)
        self.tilt_label_reading = Label(master, textvariable=self.tilt_label_text)

        self.distance_label_text = IntVar()
        self.distance_label_text.set(self.distance)
        self.distance_label_reading = Label(master, textvariable=self.distance_label_text)

        # Create entry box 
        # vcmd = master.register(self.validate) # we have to wrap the command
        # self.entry = Entry(master, validate="key", validatecommand=(vcmd, '%P'))

        # Create buttons 
        plus_one_text = "+1" 
        # plus_ten_text = "+10" 
        minus_one_text = "-1" 
        # minus_ten_text = "-10" 

        # axes = ["tip","tilt","distance"]
        # button_text = ["-10","-1","+1","+10"]

        # for i in len(button_text):
        #     self.button.append(Button(self, text='Game '+str(i+1),command=lambda:self.open_this(i)))
        #     self.button[i].grid(column=4, row=i+1, sticky=W)

        self.add_1_tip_button = Button(master, text=plus_one_text, command=lambda: self.update("add_1_tip"))
        self.add_1_tilt_button = Button(master, text=plus_one_text, command=lambda: self.update("add_1_tilt"))
        self.add_1_distance_button = Button(master, text=plus_one_text, command=lambda: self.update("add_1_distance"))
        
        self.sub_1_tip_button = Button(master, text=minus_one_text, command=lambda: self.update("sub_1_tip"))
        self.sub_1_tilt_button = Button(master, text=minus_one_text, command=lambda: self.update("sub_1_tilt"))
        self.sub_1_distance_button = Button(master, text=minus_one_text, command=lambda: self.update("sub_1_distance"))

        self.add_1_button = Button(master, text="+", command=lambda: self.update("add"))
        self.subtract_button = Button(master, text="-", command=lambda: self.update("subtract"))
        self.reset_button = Button(master, text="Reset", command=lambda: self.update("reset"))

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

        # Put labels in column 0 
        self.tip_label.grid(row=tip_row, column=label_col, sticky=label_align)
        self.tilt_label.grid(row=tilt_row, column=label_col, sticky=label_align)
        self.distance_label.grid(row=distance_row, column=label_col, sticky=label_align)

        # put position labels in column 1
        self.tip_label_reading.grid(row=tip_row, column=measure_col)
        self.tilt_label_reading.grid(row=tilt_row, column=measure_col)
        self.distance_label_reading.grid(row=distance_row, column=measure_col)

        # put subtract buttonts in column 2
        self.sub_1_tip_button.grid(row=tip_row, column=sub_1_col)
        self.sub_1_tilt_button.grid(row=tilt_row, column=sub_1_col)
        self.sub_1_distance_button.grid(row=distance_row, column=sub_1_col)

        # Put add buttons in column 3
        self.add_1_tip_button.grid(row=tip_row, column=add_1_col)
        self.add_1_tilt_button.grid(row=tilt_row, column=add_1_col)
        self.add_1_distance_button.grid(row=distance_row, column=add_1_col)
        
        # self.entry.grid(row=1, column=0, columnspan=3, sticky=W+E)


    def validate(self, new_text):
        if not new_text: # the field is being cleared
            self.entered_number = 0
            return True

        try:
            self.entered_number = int(new_text)
            return True
        except ValueError:
            return False

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
        # self.entry.delete(0, END)

root = Tk()
my_gui = Calibrate(root)
root.mainloop()