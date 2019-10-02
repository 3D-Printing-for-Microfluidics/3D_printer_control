# -*- coding: utf-8 -*-
"""Galil control module."""
import time
import json
import atexit
import gclib

# remove bad chars from file name
def cleanFileName(name):
    for c in '\\/:*?"<>| ':
        name = name.replace(c, '')
    return name

# maps X,Y,Z to A,B,C
def convertAxis(axis):
    axis = axis.upper()
    if axis in ('X', 'A'):
        return 'A'
    if axis in ('B', 'Y'):
        return 'B'
    if axis in ('C', 'Z'):
        return 'C'
    raise ValueError('Invalid axis supplied')

# return the value for the specified axis
def parseResponseString(string, axis="A"):
    string = string.replace(',', '')                # get rid of commas in response
    array = string.split()                          # split axes into an array
    axis = convertAxis(axis)                        # sterilize axis input
    axis_index = ord(axis.lower()) - 97             # converts A B C to 0 1 2
    value = array[axis_index]                       # index into the axis we want
    return int(value)

class Galil():
    def __init__(self, address=None, verbose=False):
        self.verbose = verbose
        self.address = address

        # default configuration parameters
        self.axes = ["A"]
        self.travel = {"A":100}     # max travel in mm
        self.ctspmm = {"A":8000}    # counts/mm for each axis
        self.data = {}              # for saving calibration data
        self.move_num = 0           # also for saving calibration data

        # connection parameters
        self.connected = False
        self.homed = False
        self.controller_name = "DMC31010"   # controller to search for
        self.g = gclib.py()                 # make an instance of the gclib python class
        atexit.register(self.disconnect)    # register disconnect to always run at interpreter end



        # self.encoder = Encoder(encoder_HWID)
        # self.lead_screw_pitch_mm = 0.635
        # self.encoder_counts_per_revolution = 20000
        # # self.encoder_print_file = None
        # self.loadCellPin = 4    #Just a BCM GPIO Pin
        # self.printTimer = 0

    def initialize(self):
        self.motorOn()

    def goToZmax(self):
        self.absMove(speed=20, cnts=-240000)

    def goToZmin(self):
        self.absMove(speed=20, cnts=240000)

    def resume(self, layerThickness):
        # dummy for now, to satisfy old Solus method
        pass

    def goToFirstLayerHeight(self, height):
        # dummy for now, to satisfy old Solus method
        pass

    def goToPlanarizationPullOff(self):
        pass

    def printCycle(self, layerThicknessMm, commandChain):
        self.relMove(speed=25, mm=1)
        self.relMove(speed=25, mm=layerThicknessMm - 1)



    def pause(self):
        pass
    # def initializeLoadCell(self):
    #     GPIO.setmode(GPIO.BCM)
    #     GPIO.setwarnings(False)
    #     GPIO.setup(self.loadCellPin, GPIO.OUT)
    #     GPIO.output(self.loadCellPin, 0)

    # def startLoadCell(self):
    #     GPIO.output(self.loadCellPin, 1)

    # def stopLoadCell(self):
    #     GPIO.output(self.loadCellPin, 0)

    # def getTimeRelative(self):
    #     diffTime = time.time() - self.printTimer
    #     return diffTime

    # def openEncoderFile(self, file_name):
    #     self.encoder_print_file = open(str(file_name), "a+")

    # def closeEncoderFile(self):
    #     self.encoder_print_file.close()

    # def openLoadCellFile(self, file_name):
    #     self.load_cell_file = open(str(file_name), "a+")

    # def closeLoadCellFile(self):
    #     self.load_cell_file.close()










    # find and connect to the Galil controller
    def connect(self):
        # Get Ethernet controllers requesting IP addresses
        print("Searching for {} controller...".format(self.controller_name))
        available = self.g.GAddresses()
        self.address = None
        # If there is more than one controller connected, this will only connect to the first
        for address in sorted(available.keys()):
            if self.controller_name in available[address]:
                self.address = address.strip('()')
                self.controller_name = available[address]
                if self.verbose: print("Found", available[address], "at", self.address)
                print("Connecting to {} at {}".format(self.controller_name, self.address))
                self.g.GOpen("{} --direct".format(self.address))
                if self.verbose: print("GInfo returned:", self.g.GInfo())
                self.connected = True
                return
        exit("{} not found.".format(self.controller_name))

    # convert mm to counts for the specified axis
    def mmToCnts(self, mm, axis="A"):
        axis = convertAxis(axis)
        return int(mm * self.ctspmm[axis])

    # convert counts to mm for the specified axis
    def cntsToMm(self, counts, axis="A"):
        axis = convertAxis(axis)
        return counts / self.ctspmm[axis]

   # send a command to the controller, interpret errors if any are thrown
    def send(self, command):
        if self.verbose: print("Sent : '{}'".format(command))   # print send command if in verbose mode
        try:
            response = self.g.GCommand(command)                 # send the command and save the response
            response = ''.join(response)                        # join the returned char array into a string
            if self.verbose and response != '':
                print("Reply: '{}'".format(response))           # print the response if in verbose mode
            return response                                     # return the response
        except gclib.GclibError as error:                       # if there is an error
            error_code = self.g.GCommand("TC 1")                # get the human readable error code
            if error_code not in ('', "0"):
                error = error_code
            print("Error: Last command '{}' returned error '{}'".format(command, error))
            return error

    # check both limit switches, return a tuple with their trip values
    def checkLimits(self, axis="A"):
        a = convertAxis(axis)
        lf = self.send("MG _LF{}".format(a))
        lr = self.send("MG _LR{}".format(a))
        return bool(lf == "0.0000"), bool(lr == "0.0000")

    # read the current position of the specified encoder
    def getPosition(self, axis="A"):
        if axis is None:                                        # if no axis is specified
            return self.send("TP")                              # read all axes
        axis = convertAxis(axis)                                # check that the axis is valid
        axis_position = self.send("TP{}".format(axis))          # get the encoder reading
        return int(axis_position)

    # turn on the specified axis
    def motorOn(self, axis="A"):
        axis = convertAxis(axis)                                # make sure a valid axis was supplied
        self.send("SH{}".format(axis))                          # send the motor enable command

    # turn off the specified axis
    def motorOff(self, axis="A"):
        axis = convertAxis(axis)                                # make sure a valid axis was supplied
        self.send("MO{}".format(axis))                          # send the motor off command

    # get the acceleration for the specified axis (mm/sec^2)
    def getAcceleration(self, axis="A"):
        a = convertAxis(axis)                                   # check that the axis is valid
        response = self.send("AC ?")                            # query the acceleration for all axes
        acc = parseResponseString(response, a)                  # pull out the acceleration value for the axis we care about
        return int(acc)/self.ctspmm[a]                          # convert acceleration from cnts/sec^2 to mm/sec^2

    # set the acceleration for the specified axis (mm/sec^2)
    def setAcceleration(self, acceleration, axis="A"):
        a = convertAxis(axis)                                       # check that the axis is valid
        self.send("AC{}={}".format(a, acceleration*self.ctspmm[a])) # set acceleration
        self.send("DC{}={}".format(a, acceleration*self.ctspmm[a])) # set deceleration

    # get the speed for the specified axis (mm/sec)
    def getSpeed(self, axis="A"):
        a = convertAxis(axis)                                   # check that the axis is valid
        response = self.send("SP ?")                            # query the speed for all axes
        speed = parseResponseString(response, a)                # pull out the speed value for the axis we care about
        return int(speed)/self.ctspmm[a]                        # convert speed from cnts/sec to mm/sec

    # set the speed for the specified axis (mm/sec)
    def setSpeed(self, speed, axis="A"):
        a = convertAxis(axis)                                   # check that the axis is valid
        self.send("SP{}={}".format(a, speed*self.ctspmm[a]))    # set speed

    # run the Galil homing routine
    def home(self, axis="A"):
        a = convertAxis(axis)                                   # check that the axis is valid
        self.relMove(speed=20, mm=-self.travel["A"])            # move up until the limit switch is triggered
        self.g.GMotionComplete(a)                               # block until motion planning is complete
        self.motorOn()                                          # turn motor back on (limit switch was tripped, which turns it off)
        self.send("HM")                                         # send home command
        self.send("BGA")                                        # start homing
        self.waitForMotionComplete(0)                           # block until motion is complete (encoder is set to 0 at end of homing)
        self.homed = True                                       # update class homed status

    # blocking call to relative move an axis the specified distance at speed (in mm/sec)
    # pylint: disable=too-many-arguments
    def relMove(self, speed, mm=None, cnts=None, acceleration=None, axis="A"):
        a = convertAxis(axis)                                   # check that the axis is valid
        old_speed = self.getSpeed()                             # record the previous speed
        old_acceleration = self.getAcceleration()               # record the previous acceleration
        self.setSpeed(speed)                                    # set speed (mm/sec)
        if acceleration is not None:                            # if acceleration is going to be altered
            self.setAcceleration(acceleration)                  # change it
        if mm is not None:                                      # if mm were supplied
            cnts = self.mmToCnts(mm)                            # convert to counts
        if cnts is not None:                                    # if counts has been calculated or supplied
            start_position = self.getPosition()                 # save the starting position
            self.send("PR{}={}".format(a, cnts))                # move desired distance
            self.send("BG{}".format(a))                         # begin motion
            self.waitForMotionComplete(start_position + cnts)   # block until motion is complete
        self.setSpeed(old_speed)                                # restore previous speed
        if acceleration is not None:                            # if acceleration was altered
            self.setAcceleration(old_acceleration)              # change it back to the old value

    # blocking call to move specified axis to absolute position at speed (in mm/sec)
    # pylint: disable=too-many-arguments
    def absMove(self, speed, mm=None, cnts=None, acceleration=None, axis="A"):
        if not self.homed:
            exit("Must home before using absolute movements!")  # make sure stage is homed before any absolute moves are tried
        a = convertAxis(axis)                                   # check that the axis is valid
        old_speed = self.getSpeed()                             # record the previous speed
        old_acceleration = self.getAcceleration()               # record the previous acceleration
        self.setSpeed(speed)                                    # set speed (mm/sec)
        if acceleration is not None:                            # if acceleration is going to be altered
            self.setAcceleration(acceleration)                  # change it
        if mm is not None:                                      # if mm were supplied
            cnts = self.mmToCnts(mm)                            # convert to counts
        if cnts is not None:                                    # if counts has been calculated or supplied
            self.send("PA{}={}".format(a, cnts))                # move to target position
            self.send("BG{}".format(a))                         # begin motion
            self.waitForMotionComplete(cnts)                    # wait for physical motion to complete
        self.setSpeed(old_speed)                                # restore previous speed
        if acceleration is not None:                            # if acceleration was altered
            self.setAcceleration(old_acceleration)              # change it back to the old value

    # blocks execution until the encoder reading reaches the specified value. Also logs all position data
    def waitForMotionComplete(self, cnts, axis="A"):
        start_time = time.time()
        last_position = self.getPosition()                      # save the last position
        self.data[self.move_num] = []
        self.data[self.move_num].append({'time' : time.time(), 'position' : last_position})
        counter = 0
        time_count = 0
        while counter <= 10:                                    # only proceed when 10 good consecutive counts have been read
            time.sleep(0.001)                                   # wait 1 ms
            last_position = self.getPosition()                  # read position again
            if any(self.checkLimits()):                         # finish early if a limit is tripped
                print("Limit switch triggered")                 # notify user of limit
                self.g.GMotionComplete(axis)                    # wait for controller planning to finish
                return
            self.data[self.move_num].append({'time' : time.time(), 'position' : last_position})
            if int(cnts - 1) <= last_position <= int(cnts + 1):
                counter += 1
            else:
                counter = 0
            time_count += 1
            if time_count >= 5000:                              # timeout for collecting data, motor won't reach position
                exit("Z motor didn't reach position. Got to {} but needed {}".format(last_position, cnts))
                break
        self.data[self.move_num].append({'duration' : time.time()-start_time})
        self.move_num = self.move_num + 1

    # save motion data to a file
    def saveMotionData(self, filename=None):
        # save the coefficients for this run
        for coeff in ("KP", "KI", "KD", "IL"):
            response = self.send("{} ?,?,?".format(coeff))
            response = response.replace(',', '')                # get rid of commas in response
            response = response.split()                         # split axes into an array
            self.data['{}C'.format(coeff)] = response[2]        # get C axis which will be at index 2
        # save the file
        if filename is None:
            filename = "galil_data_P={}_I={}_D={}_IL={}.txt".format(self.data['KPC'], self.data['KIC'], self.data['KDC'], self.data['ILC'])
        filename = cleanFileName(filename)
        with open(filename, 'w') as outfile:
            json.dump(self.data, outfile)

    # end connection
    def disconnect(self):
        if self.connected is not False:
            try:
                self.connected = False
                self.g.GClose()                                 # don't forget to close connections!
                if self.verbose: print("Disconnected from", self.controller_name)
            except gclib.GclibError as e:
                print('Unexpected GclibError on disconnect:', e)

    # this only needs to be run once on power up. It will turn off motors which may cause movement, BE CAREFUL
    def configure(self):
        # Setup
        self.send("MO")             # turns off motors (motors must be off to set some of these values)
        self.send("AF 0")           # configures analog feedback mode for the PID filter - "0" means use analog
        self.send("AG 1")           # sets the amplifier current/voltage gain for the internal amplifier - for DMC-3x012 "0" -> 0.4 A/V, "1" -> 0.8 A/V, "2" -> 1.6 A/V
        self.send("AU 8.0")         # sets the amplifier current loop gain for internal amplifiers - see command reference for appropriate values
        self.send("BL -2147483648") # sets the reverse software limit - thisvalue effectively disables the limit
        self.send("BM 5333.3333")   # sets brushless modulus - counts/revolution of the motor divided by the number of pole pairs of the motor. For a linear motor, it is the number of encoder counts per magnetic phase
        self.send("BW 0")           # sets the delay between when the brake is turned on and when the amp is turned off (in samples)
        self.send("CE 0")           # configures the encoder - "0" means use normal quadrature, "2" means reversed quadrature
        self.send("CN 1")           # sets limit switchtes to be treated as active high
        self.send("ER 4000")        # sets error limit - motor will shut down if this is exceeded. Can see current error with TE
        self.send("FA 0")           # sets the acceleration feedforward coefficient
        self.send("FL 2147483647")  # sets forward software limit - this value effectively disables the limit
        self.send("FV 0")           # sets the velocity feedforward coefficient
        self.send("HV 4000")        # sets the slew speed for the FI final move to the index and all but the first stage of HM
        self.send("IT 0.5000")      # sets the bandwidth of the motion smooting filter - see command reference for details
        self.send("LC 0")           # enables low current mode for stepper motors. Low current mode reduces the holding current of the stepper motors while at rest. "0" means use full current
        self.send("LD 0")           # enable both forward and rear limit switches
        self.send("MT 1.0")         # selects the type of the motor and the polarity of the drive signal - "1" means servo motor with normal signal, "-1" means reversed polarity
        self.send("NB 0.5")         # sets real part of the notch poles - controls the range of frequencies that will be attenuated
        self.send("NF 0")           # sets the frequency of the notch filter, which is placed in series with the PID compensation
        self.send("OE 1")           # sets the Off On Error function for the controller - if position exceeds this error, motor will shut off
        self.send("OF 0.0000")      # sets a bias voltage in the command output - useful to hold stage when upright if necessary
        self.send("PL 0.0000")      # adds a low-pass filter in series with the PID compensation
        self.send("SD 256000")      # sets the switch decelleration
        self.send("TM 1000.0000")   # set sampling period of control loop - TM 1000 will actually set an update rate of 976 microseconds (this is the default value). Thus the value returned by the TIME operand will be off by 2.4% of the actual time
        self.send("TK 8.5002")      # sets peak torque limit (may momentarily exceed TL below) - see command reference to learn how to calculate
        self.send("TL 4.2")         # sets torque limit
        self.send("YA 2")           # specifies the microstepping resolution of the step drive in microsteps per full motor step - "2" means use half stepping

        # Tuning
        self.send("KP 59.6250")     # sets the proportional constant in the controller filter
        self.send("KI 2.8711")      # sets the integral gain of the control loop
        self.send("KD 445.8750")    # sets the derivative constant in the control filter
        self.send("IL 9.9982")      # limits the effect of the integrator gain in the filter to a certain voltage

        # Sine amp initialization
        # self.send("BI -1")          # don't use the dedicated hall inputs to run initialization of the sinusoidal driver - better to use the automated tool than this
        # self.send("BX< 200")        # run initialization of sinusoidal amplifier and limit initialization time to 200ms
        # self.send("BZ -4")          # don't use the dedicated hall inputs to run initialization of the sinusoidal driver - better to use the automated tool than this

    # downlaod a DMC file to the controller
    def downloadProgram(self, filename):
        print("Downloading \"{}\" to controller...".format(filename))
        return self.g.GProgramDownloadFile(filename)

    # interactive mode - will return a prompt you can issue Galil commands to. Exits with KeyboardInterrupt
    def interactiveMode(self):
        if not self.connected:
            exit("Must be connected to Galil controller to run interactive mode")
        try:
            while True:
                cmd = input("Give Galil a command>> ")
                cmd.strip()
                print(self.send(cmd.upper()))
        except KeyboardInterrupt:
            print("\nExited by KeyboardInterrupt")


# runs if called from the console
if __name__ == '__main__':
    g = Galil(verbose=False)
    g.connect()
    g.interactiveMode()

    # g.motorOn()
    # g.home()
    # for _ in range(5):
    #     g.relMove(speed=10, mm=10)
    #     g.relMove(speed=10, mm=-10)




# import serial
# import serial.tools.list_ports
# import serial.serialutil

# import RPi.GPIO as GPIO

# encoder_HWID = '16C0:0483'      ##This is the HWID of the Teensy

# def findACMport(hwid):
#     ports = list(serial.tools.list_ports.comports())
#     for p in ports:
#         if 'ttyACM' in p.name:
#             print("Found", p.device)
#             if hwid in p.hwid:
#                 return p.device

# class Encoder(serial.Serial):
#     def __init__(self, hwid, verbose=False):
#         super().__init__(baudrate=115200, timeout=None)
#         time.sleep(.5)
#         self.verbose = verbose
#         self.hwid = hwid

#     def connect(self):
#         self.port = findACMport(self.hwid)
#         print("self.port: ", self.port)
#         if self.port is None:
#             raise ValueError('Encoder not found')
#         elif self.is_open:
#             self.close()
#         print("Connecting to Encoder Port:", self.port)
#         self.open()
#         time.sleep(.1)
#         # self.flush()
#         # self.reset_input_buffer()
#         # self.reset_output_buffer()

#     def readEncoder(self):
#         # print("encoder read 1")
#         # self.flushInput()
#         # self.flushOutput()
#         self.write('1'.encode())
#         self.flushInput()
#         # self.flushOutput()
#         # self.write(1)
#         # time.sleep(.125)
#         # print("encoder read 2")
#         # for i in range(10):
#         #     data = self.readline()
#         #     print(i, data)
#         # garbage = self.readline()
#         data = self.readline()
#         # data2 = self.readline()
#         # data3 = self.readline()
#         # data4 = self.readline()
#         # data = self.readall()
#         # data2 = self.read()
#         # print(data2)
#         # print("readline: ", data)
#         # print("data2: ", data2)
#         # print("data3: ", data3)
#         # print("data4: ", data4)
#         data = data.decode()
#         print("decoded: ", data)
#         data = data.strip()
#         print("stripped: ", data)
#         print("data: ", data)
#         if data:
#             print("a")
#             counts = int(data)
#         else:
#             print("b")
#             counts = -1
#         # self.flush()
#         # self.reset_input_buffer()
#         # self.reset_output_buffer()
#         print(counts)
#         return counts
#         # return int.from_bytes(data)

#     def writeEncoder(self, value=0):
#         self.write(value.encode())



"""

Homing fails if above hall sensor

how to tell when physical motion to complete


make sure you are on the right side of the switch


sensor is backwards

CE - invert encoder
invert switches




"""