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
        self.controller_name = "DMC31010"   # controller to search for
        self.g = gclib.py()                 # make an instance of the gclib python class
        atexit.register(self.disconnect)    # register disconnect to always run at interpreter end

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
                return True
        print(self.controller_name, "not found.")
        return False    # no controller found

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
        return self.send("AC{} ?".format(a))                    # return the acceleration

    # set the acceleration for the specified axis (mm/sec^2)
    def setAcceleration(self, acceleration, axis="A"):
        a = convertAxis(axis)                                       # check that the axis is valid
        self.send("AC{}={}".format(a, acceleration*self.ctspmm[a])) # set acceleration
        self.send("DC{}={}".format(a, acceleration*self.ctspmm[a])) # set deceleration

    # get the speed for the specified axis (mm/sec)
    def getSpeed(self, axis="A"):
        a = convertAxis(axis)                                   # check that the axis is valid
        return self.send("SP{} ?".format(a))                    # return the speed

    # set the speed for the specified axis (mm/sec)
    def setSpeed(self, speed, axis="A"):
        a = convertAxis(axis)                                   # check that the axis is valid
        self.send("SP{}={}".format(a, speed*self.ctspmm[a]))    # set speed

    # run the Galil homing routine
    def home(self, axis="A"):
        a = convertAxis(axis)                                   # check that the axis is valid
        self.send("HM")                                         # send home command
        self.send("BGA")                                        # start homing
        self.g.GMotionComplete(a)                               # block until motion is complete

    # blocking call to relative move an axis the specified distance at speed (in mm/sec)
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
            self.send("PR{}={}".format(a, -8000))               # move down 1mm
            self.send("BG{}".format(a))                         # begin motion
            self.g.GMotionComplete(a)                           # block until motion is complete
            self.send("PR{}={}".format(a, 8000 + cnts))         # move up 1mm + the desired distance
            self.send("BG{}".format(a))                         # begin motion
            self.waitForMotionComplete(start_position + cnts)   # block until motion is complete
        self.setSpeed(old_speed)                                # restore previous speed
        if acceleration is not None:                            # if acceleration was altered
            self.setAcceleration(old_acceleration)              # change it back to the old value

    # blocking call to move specified axis to absolute position at speed (in mm/sec)
    def absMove(self, speed, mm=None, cnts=None, acceleration=None, axis="A"):
        a = convertAxis(axis)                                   # check that the axis is valid
        old_speed = self.getSpeed()                             # record the previous speed
        old_acceleration = self.getAcceleration()               # record the previous acceleration
        self.setSpeed(speed)                                    # set speed (mm/sec)
        if acceleration is not None:                            # if acceleration is going to be altered
            self.setAcceleration(acceleration)                  # change it
        if mm is not None:                                      # if mm were supplied
            cnts = self.mmToCnts(mm)                            # convert to counts
        if cnts is not None:                                    # if counts has been calculated or supplied
            self.send("PA{}={}".format(a, cnts - 8000))         # move down the distance you want, and then 1mm further
            self.send("BG{}".format(a))                         # begin motion
            self.g.GMotionComplete(a)                           # block until motion is complete
            self.send("PR{}={}".format(a, 8000))                # move up 1mm
            self.send("BG{}".format(a))                         # begin motion
            self.waitForMotionComplete(cnts)                    # wait for physical motion to complete
        self.setSpeed(old_speed)                                # restore previous speed
        if acceleration is not None:                            # if acceleration was altered
            self.setAcceleration(old_acceleration)              # change it back to the old value

    # blocks execution until the encoder reading reaches the specified value. Also logs all position data
    def waitForMotionComplete(self, cnts):
        start_time = time.time()
        last_position = self.getPosition()                      # save the last position
        self.data[self.move_num] = []
        self.data[self.move_num].append({'time' : time.time(), 'position' : last_position})
        counter = 0
        time_count = 0
        while counter <= 10:                                    # only proceed when 10 good consecutive counts have been read
            time.sleep(0.001)                                   # wait 1 ms
            last_position = self.getPosition()                  # read position again
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
        self.send("TM 1000.0000")   # set sampling period of control loop - TM 1000 will actually set an update rate of 976 microseconds (this is the default value). Thus the value returned by the TIME operand will be off by 2.4% of the actual time
        self.send("AG 1")           # sets the amplifier current/voltage gain for the internal amplifier - for DMC-3x012 "0" -> 0.4 A/V, "1" -> 0.8 A/V, "2" -> 1.6 A/V
        self.send("OF 0.0000")      # sets a bias voltage in the command output - useful to hold stage when upright if necessary
        self.send("AU 8.0")         # sets the amplifier current loop gain for internal amplifiers - see command reference for appropriate values
        self.send("LD 0")           # enable both forward and rear limit switches
        self.send("OE 1")           # sets the Off On Error function for the controller - if position exceeds this error, motor will shut off
        self.send("ER 4000")        # sets error limit - motor will shut down if this is exceeded. Can see current error with TE
        self.send("CN -1")          # sets limit switchtes to be treated as active high
        self.send("AF 0")           # configures analog feedback mode for the PID filter - "0" means use analog
        self.send("CE 2")           # configures the encoder - "0" means use normal quadrature, "2" means reversed quadrature
        self.send("MT -1.0")        # selects the type of the motor and the polarity of the drive signal - "1" means servo motor with normal signal, "-1" means reversed polarity
        self.send("BW 0")           # sets the delay between when the brake is turned on and when the amp is turned off (in samples)
        self.send("FL 2147483647")  # sets forward software limit - this value effectively disables the limit
        self.send("BL -2147483648") # sets the reverse software limit - thisvalue effectively disables the limit
        self.send("TK 8.5002")      # sets peak torque limit (may momentarily exceed TL below) - see command reference to learn how to calculate
        self.send("TL 4.2")         # sets torque limit

        # Tuning
        self.send("KP 59.6250")     # sets the proportional constant in the controller filter
        self.send("KI 2.8711")      # sets the integral gain of the control loop
        self.send("KD 445.8750")    # sets the derivative constant in the control filter
        self.send("IL 9.9982")      # limits the effect of the integrator gain in the filter to a certain voltage
        self.send("PL 0.0000")      # adds a low-pass filter in series with the PID compensation
        self.send("NB 0.5")         # sets real part of the notch poles - controls the range of frequencies that will be attenuated
        self.send("NF 0")           # sets the frequency of the notch filter, which is placed in series with the PID compensation

        # Motion Settings
        self.send("SD 256000")      # sets the switch decelleration
        self.send("FA 0")           # sets the acceleration feedforward coefficient
        self.send("FV 0")           # sets the velocity feedforward coefficient
        self.send("HV 4000")        # sets the slew speed for the FI final move to the index and all but the first stage of HM
        self.send("IT 0.5000")      # sets the bandwidth of the motion smooting filter - see command reference for details
        self.send("LC 0")           # enables low current mode for stepper motors. Low current mode reduces the holding current of the stepper motors while at rest. "0" means use full current
        self.send("YA 2")           # specifies the microstepping resolution of the step drive in microsteps per full motor step - "2" means use half stepping
        self.send("BM 5333.3333")   # sets brushless modulus - counts/revolution of the motor divided by the number of pole pairs of the motor. For a linear motor, it is the number of encoder counts per magnetic phase
        self.send("BX< 200")        # run initialization of sinusoidal amplifier and limit initialization time to 200ms
        # self.send("BI 0")           # don't use the dedicated hall inputs to run initialization of the sinusoidal driver - better to use the automated tool than this
        self.send("BZ -4")          # don't use the dedicated hall inputs to run initialization of the sinusoidal driver - better to use the automated tool than this

    # downlaod a DMC file to the controller
    def downloadProgram(self, filename):
        print("Downloading \"{}\" to controller...".format(filename))
        return self.g.GProgramDownloadFile(filename)

    # interactive mode - will return a prompt you can issue Galil commands to. Exits with KeyboardInterrupt
    def interactiveMode(self):
        try:
            while True:
                cmd = input("Give Galil a command>> ")
                cmd.strip()
                self.send(cmd.upper())
        except KeyboardInterrupt:
            pass


# runs if called from the console
if __name__ == '__main__':
    g = Galil(verbose=False)
    g.connect()
    # g.configure()
    # print(g.getPosition())
    # g.home()
    print(g.getPosition())
    g.relMove(speed=10, mm=20)
    print(g.getPosition())
    g.relMove(speed=10, mm=-20)
    print(g.getPosition())
    g.absMove(speed=10, mm=-20)
    print(g.getPosition())
    g.absMove(speed=10, mm=0)
    print(g.getPosition())

    # g.interactiveMode()

    print("Done")


## Add TC - tell error code - will tell you why things aren't working