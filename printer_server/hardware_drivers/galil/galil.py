# -*- coding: utf-8 -*-
"""Galil control module."""
import re
import time
import json
import atexit
from pathlib import Path
from datetime import datetime

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

    # regular expressions for parsing command chains
    waitRegex = re.compile(r'WAIT (-?\d+(\.\d+)?)')
    moveRegex = re.compile(r'^(UP|DOWN) (-?\d+(\.\d+)?) SPEED (-?\d+(\.\d+)?) ACC (-?\d+(\.\d+)?)')

    def __init__(self, address=None, verbose=False):

        # import here so test system doesn't have to install gclib
        import gclib
        self.gclib_error = gclib.GclibError

        self.verbose = verbose
        self.address = address
        self.bottom_position = 368000
        self.top_position = -400000
        self.error_window = 1

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

        # a log with all IO sent to the controller
        self.log = Path.cwd() / 'logs'      # a log to track all communications for debugging, gets created on connect

    def initialize(self):
        self.motorOn()

    def goToZmax(self):
        self.absMove(speed=25, cnts=self.top_position)
        self.waitForMotionComplete(self.top_position)
        return self.getPosition()

    def goToZmin(self):
        self.absMove(speed=25, cnts=self.bottom_position)
        self.waitForMotionComplete(self.bottom_position)
        return self.getPosition()

    def resume(self, layerThickness):
        # dummy for now, to satisfy old Solus method
        pass

    def goToFirstLayerHeight(self, layerThickness):
        cnts = self.bottom_position - self.mmToCnts(layerThickness)
        start_position = self.getPosition()
        self.absMove(speed=25, cnts=cnts)
        end_position = self.getPosition()
        return start_position, end_position

    def goToPlanarizationPullOff(self):
        pass

    def printCycle(self, layerThicknessMm, commandChain):
        start_time = datetime.now()
        start_position = self.getPosition()

        # keep track of which command is the last down command
        lastDownCommand = 0
        for i, command in enumerate(commandChain):
            m2 = self.moveRegex.fullmatch(command)
            if m2 and m2.group(1) == 'DOWN':
                lastDownCommand = i

        # parse the commands and move accordingly
        for i, command in enumerate(commandChain):
            m1 = self.waitRegex.fullmatch(command)
            m2 = self.moveRegex.fullmatch(command)
            if m1:                                              # is a wait command
                wait_seconds = float(m1.group(1))
                time.sleep(wait_seconds)
            elif m2:                                            # is a move command
                direction = m2.group(1)
                distance = float(m2.group(2))
                speed = float(m2.group(4))
                acceleration = float(m2.group(6))
                distance *= -1 if direction == 'UP' else 1      # calculate the sign using direction, up is negative
                if i == lastDownCommand:                        # take off the layer thickness if this is the last downward move
                    distance -= layerThicknessMm
                self.relMove(speed=speed, mm=distance, acceleration=acceleration)

        # report starting and ending positions
        end_position = self.getPosition()
        end_time = datetime.now()
        return start_position, end_position, start_time, end_time

    def pause(self):
        pass

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

                # Create log
                date_and_time = datetime.now().strftime('%Y_%m_%d-%H_%M_%S')
                self.log = str(self.log / 'galil_controller_command_dump_{}.txt'.format(date_and_time))

                # all done, return control
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
    def send(self, command, notify=True):
        with open(self.log, "a") as f:
            if self.verbose and notify:
                print("Sent : '{}'".format(command))                    # print send command if in verbose mode
                f.write("Sent : '{}'\n".format(command))            # record sent command in log file
            try:
                response = self.g.GCommand(command)                 # send the command and save the response
                response = ''.join(response)                        # join the returned char array into a string
                if self.verbose and notify and response != '':
                    f.write("Reply: '{}'\n".format(response))           # record reply in log file
                    print("Reply: '{}'".format(response))           # print the response if in verbose mode
                return response                                     # return the response
            except self.gclib_error as error:                       # if there is an error
                error_code = self.g.GCommand("TC 1")                # get the human readable error code
                if error_code not in ('', "0"):
                    error = error_code
                print("Error: Last command '{}' returned error '{}'".format(command, error))
                return error

    # check both limit switches, return a tuple with their trip values
    def checkLimits(self, axis="A"):
        a = convertAxis(axis)
        lf = self.send("MG _LF{}".format(a), notify=False)
        lr = self.send("MG _LR{}".format(a), notify=False)
        return bool(lf == "0.0000"), bool(lr == "0.0000")

    # read the current position of the specified encoder
    def getPosition(self, axis="A", notify=True):
        if axis is None:                                        # if no axis is specified
            return self.send("TP", notify=notify)               # read all axes
        axis = convertAxis(axis)                                # check that the axis is valid
        pos = self.send("TP{}".format(axis), notify=notify)     # get the encoder reading
        return int(pos)

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
        response = self.send("AC ?", notify=False)              # query the acceleration for all axes
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
        response = self.send("SP ?", notify=False)              # query the speed for all axes
        speed = parseResponseString(response, a)                # pull out the speed value for the axis we care about
        return int(speed)/self.ctspmm[a]                        # convert speed from cnts/sec to mm/sec

    # set the speed for the specified axis (mm/sec)
    def setSpeed(self, speed, axis="A"):
        a = convertAxis(axis)                                   # check that the axis is valid
        self.send("SP{}={}".format(a, speed*self.ctspmm[a]))    # set speed in mm/sec

    # run the Galil homing routine
    def home(self, axis="A"):
        a = convertAxis(axis)                                   # check that the axis is valid
        self.motorOn()                                          # turn motor on
        self.relMove(speed=25, mm=-self.travel["A"])            # move up until the limit switch is triggered
        self.g.GMotionComplete(a)                               # block until motion planning is complete
        self.motorOn()                                          # turn motor back on (limit switch was tripped, which turns it off)
        self.send("HM")                                         # send home command
        self.send("BGA")                                        # start homing
        self.waitForMotionComplete(0)                           # block until motion is complete (encoder is set to 0 at end of homing)
        self.homed = True                                       # update class homed status

    # blocking call to relative move an axis the specified distance at speed (in mm/sec)
    # pylint: disable=too-many-arguments
    def relMove(self, mm=None, cnts=None, speed=None, acceleration=None, axis="A"):
        a = convertAxis(axis)                                   # check that the axis is valid
        old_speed = None
        old_acceleration = None
        if speed is not None:                                   # if speed is going to be altered
            old_speed = self.getSpeed()                         # record the previous speed
            self.setSpeed(speed)                                # set speed (mm/sec)
        if acceleration is not None:                            # if acceleration is going to be altered
            old_acceleration = self.getAcceleration()           # record the previous acceleration
            self.setAcceleration(acceleration)                  # change it
        if mm is not None:                                      # if mm were supplied
            cnts = self.mmToCnts(mm)                            # convert to counts
        if cnts is not None:                                    # if counts has been calculated or supplied
            start_position = self.getPosition()                 # save the starting position
            self.send("PR{}={}".format(a, cnts))                # move desired distance
            self.send("BG{}".format(a))                         # begin motion
            self.waitForMotionComplete(start_position + cnts)   # block until motion is complete
        if speed is not None:                                   # if speed was altered
            self.setSpeed(old_speed)                            # restore previous speed
        if acceleration is not None:                            # if acceleration was altered
            self.setAcceleration(old_acceleration)              # change it back to the old value
        return self.getPosition()

    # blocking call to move specified axis to absolute position at speed (in mm/sec)
    # pylint: disable=too-many-arguments
    def absMove(self, mm=None, cnts=None, speed=None, acceleration=None, axis="A"):
        if not self.homed:
            exit("Must home before using absolute movements!")  # make sure stage is homed before any absolute moves are tried
        a = convertAxis(axis)                                   # check that the axis is valid
        old_speed = None
        old_acceleration = None
        if speed is not None:                                   # if speed is going to be altered
            old_speed = self.getSpeed()                         # record the previous speed
            self.setSpeed(speed)                                # set speed (mm/sec)
        if acceleration is not None:                            # if acceleration is going to be altered
            old_acceleration = self.getAcceleration()           # record the previous acceleration
            self.setAcceleration(acceleration)                  # change it
        if mm is not None:                                      # if mm were supplied
            cnts = self.mmToCnts(mm)                            # convert to counts
        if cnts is not None:                                    # if counts has been calculated or supplied
            self.send("PA{}={}".format(a, cnts))                # move to target position
            self.send("BG{}".format(a))                         # begin motion
            self.waitForMotionComplete(cnts)                    # wait for physical motion to complete
        if speed is not None:                                   # if speed was altered
            self.setSpeed(old_speed)                            # restore previous speed
        if acceleration is not None:                            # if acceleration was altered
            self.setAcceleration(old_acceleration)              # change it back to the old value
        return self.getPosition()

    # blocks execution until the encoder reading reaches the specified value. Also notifys all position data
    def waitForMotionComplete(self, cnts, axis="A"):
        start_time = time.time()
        last_position = self.getPosition(notify=False)             # save the last position
        self.data[self.move_num] = []
        self.data[self.move_num].append({'time' : time.time(), 'position' : last_position})
        counter = 0
        time_count = 0
        while counter <= 10:                                    # only proceed when 10 good consecutive counts have been read
            time.sleep(0.001)                                   # wait 1 ms
            last_position = self.getPosition(notify=False)      # read position again
            if any(self.checkLimits()):                         # finish early if a limit is tripped
                print("Limit switch triggered")                 # notify user of limit
                self.g.GMotionComplete(axis)                    # wait for controller planning to finish
                return
            self.data[self.move_num].append({'time' : time.time(), 'position' : last_position})
            if int(cnts - self.error_window) <= last_position <= int(cnts + self.error_window):
                counter += 1
            else:
                counter = 0
            time_count += 1
            if time_count >= 1000:                              # timeout for collecting data, motor won't reach position
                print("Warning - Z motor didn't reach position. Got to {} but needed {}".format(last_position, cnts))
                with open(self.log, "a") as f:
                    f.write("Warning - possible position error got to {} needed {}".format(last_position, cnts))  # record sent command in log file
                # exit("Z motor didn't reach position. Got to {} but needed {}".format(last_position, cnts))
                break
        self.data[self.move_num].append({'time' : time.time(), 'position' : last_position})
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
            except self.gclib_error as e:
                print('Unexpected GclibError on disconnect:', e)

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
    # g.home()
    # error_array = []
    # g.motorOn()
    # print(g.getPosition())
    # g.send("DP 0")
    # print(g.getPosition())
    # prev = 0
    # for layer in range(100):

    #     target = -layer*80
    #     thickness = 80

    #     dist = -1
    #     start = g.getPosition()
    #     g.relMove(speed=25, mm=dist)
    #     end = g.getPosition()

    #     dist = 0.99
    #     middle = g.getPosition()
    #     g.relMove(speed=25, mm=dist)
    #     end = g.getPosition()

    #     error = thickness + end - prev
    #     actual_thickness = end - prev

    #     print("start", start, "middle", middle, "end", end, "thickness", actual_thickness, "error", error)
    #     prev = end
    #     error_array.append(error)

    # print("accumulated error", sum(error_array))
