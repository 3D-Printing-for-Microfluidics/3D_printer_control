# # -*- coding: utf-8 -*-
# """Solus module."""
# import serial
# import serial.tools.list_ports
# import serial.serialutil
# import re
# import time

# import RPi.GPIO as GPIO

# __all__ = ['Solus']
# encoder_HWID = '16C0:0483'      ##This is the HWID of the Teensy

# class Encoder(serial.Serial):
#     def __init__(self, hwid, verbose = False):
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
#         if len(data) > 0:
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
#         self.write('0'.encode())


# class Solus(serial.Serial):
#     def __init__(self, hwid, verbose=True):
#         super().__init__(baudrate=115200, timeout=None)
#         self.verbose = verbose
#         self.hwid = hwid
#         self.location = '1-1.2'
#         self.regex = re.compile(r'^(BP|QW) (UP|DOWN) (-?\d+(\.\d+)?) SPEED (\d+)')
#         self.encoder = Encoder(encoder_HWID)
#         self.lead_screw_pitch_mm = 0.635
#         self.encoder_counts_per_revolution = 20000
#         # self.encoder_print_file = None
#         self.loadCellPin = 4    #Just a BCM GPIO Pin
#         self.printTimer = 0

#     def initializeLoadCell(self):
#         GPIO.setmode(GPIO.BCM)
#         GPIO.setwarnings(False)
#         GPIO.setup(self.loadCellPin, GPIO.OUT)
#         GPIO.output(self.loadCellPin, 0)

#     def startLoadCell(self):
#         GPIO.output(self.loadCellPin, 1)

#     def stopLoadCell(self):
#         GPIO.output(self.loadCellPin, 0)

#     def getTimeRelative(self):
#         diffTime = time.time() - self.printTimer
#         return diffTime

#     def openEncoderFile(self, file_name):
#         self.encoder_print_file = open(str(file_name), "a+")

#     def closeEncoderFile(self):
#         self.encoder_print_file.close()

#     def openLoadCellFile(self, file_name):
#         self.load_cell_file = open(str(file_name), "a+")

#     def closeLoadCellFile(self):
#         self.load_cell_file.close()


#     def connect(self):
#         self.encoder.connect()

#         self.port = findUsbPort(self.hwid)
#         if self.port is None:
#             raise ValueError('BP and QW not found')
#         elif self.is_open:
#             self.close()
#         print("Connecting to", self.port, "...")
#         self.open()
#         self.reset_input_buffer()
#         self.reset_output_buffer()
#         self.initializeLoadCell()
#         return self.send("G4 P0")   # send a G4 P0 command so you get a response, even if the startup message doesn't appear

#         # self.reset_output_buffer()
#     def goToZmax(self):
#         response =  self.send('G90')          # set positioning to absolute
#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("goToZmax start: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))
#         response += self.send('G1 Z-65 F800') # send the platform to 65 mm above the quartz
#         self.transmit('G4 P0')
#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("goToZmax end: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))
#         return response

#     def initialize(self):
#         # self.encoder_initialization_write_file = open("encoder_initialization_write_file.txt", "a+")
#         # self.encoder_print_file.write("initalize start home sequence: {:d}".format(self.encoder.readEncoder()))
#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("initialize start home sequence: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))
#         response =  self.send('$H')           # calibrate the axes
#         self.transmit('G4 P0')
#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("initialize end home sequence: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))
#         response =  self.send('G90')          # set positioning to absolute
#         response += self.send('G21')          # set unit to mm
#         response += self.goToZmax()           # go to top position
#         # self.encoder_initialization_write_file.close()
#         return response

#     def goToPlanarizationPullOff(self):
#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("goToPlanarizationPullOff start: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))
#         self.send('G1 Z-5 F100')
#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("goToPlanarizationPullOff end: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))

#     def goToZmin(self):
#         # send the platform to 0
#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("goToZmin start: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))
#         response = self.send('G1 Z-5 F800')
#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("goToZmin deccel: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))
#         response = self.send('G1 Z-1 F20')
#         self.transmit('G4 P0')
#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("goToZmin end: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))
#         return response

#     def goToFirstLayerHeight(self, height):
#         self.printTimer = time.time()
#         self.startLoadCell()
#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("goToFirstLayerHeight start: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))
#         self.load_cell_file.write("goToFirstLayerHeight start: %f \r\n" %(self.getTimeRelative()))
#         response =  self.send('G1 Z-{:.4f} F600'.format(height))
#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("goToFirstLayerHeight stop: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))
#         self.load_cell_file.write("goToFirstLayerHeight end: %f \r\n" %(self.getTimeRelative()))
#         response += self.send('G91')    # set positioning to relative
#         # self.stopLoadCell()
#         return response

#     def printCycle(self, layerThicknessMm, commandChain):
#         # Command chain is the series of commands for this layer
#         # i.e. ['WAIT 0.1', 'BP UP 1 SPEED 400', 'QW DOWN 3 SPEED 300', 'WAIT 1.0',
#         #       'BP UP 2 SPEED 400', 'QW UP 3 SPEED 300', 'BP DOWN 3.00 SPEED 400', 'WAIT 1.0']

#         # find the index of the last BP command and save it. -1 means there was none
#         lastBPindex = -1
#         for i in range(0,len(commandChain)):
#             if commandChain[i].startswith('BP'):
#                 lastBPindex = i

#         # alter the last BP command (take off layer thickness), execute all others
#         for i in range(0,len(commandChain)):
#             if i == lastBPindex:
#                 lastBpCommand = commandChain[lastBPindex].split()
#                 distance = float(lastBpCommand[2])
#                 speed = lastBpCommand[4]
#                 newCommand = 'BP DOWN {:.4f} SPEED {}'.format(distance-layerThicknessMm, speed)
#                 self.execute(newCommand)
#             else:
#                 self.execute(commandChain[i])

#         # move up by layerThicknessMm if no BP command was supplied
#         if lastBPindex ==-1:
#             self.execute('BP UP {:.4f} SPEED 400'.format(layerThicknessMm))

#     def execute(self, command):
#         # Example: `WAIT 1.5` => `time.sleep(1.5)`
#         if command.startswith('WAIT'):
#             time.sleep(float(command.split()[1]))
#             return

#         m = self.regex.fullmatch(command)
#         if m:
#             direction = m.group(2)
#             distance = float(m.group(3))
#             speed = int(m.group(5))
#             if m.group(1) == 'BP':
#                 self.moveZ(direction, distance, speed)
#             elif m.group(1) == 'QW':
#                 self.moveX(direction, distance, speed)

#     def pause(self):
#         """What solus does after a print is paused"""
#         return self.moveZ('UP', 5, 400)

#     def resume(self, layerThickness):
#         """Resume after pausing"""
#         return self.moveZ('DOWN', 5-layerThickness, 400)

#     def moveX(self, direction, distance, speed):
#         """Move quartz window up/down a certain distance at a
#         given speed.

#         :param str direction: can only be 'UP' or 'DOWN'
#         :param distance: distance in millimeters.
#         :param speed: Always treated as positive. The unit is mm/min.
#         """
#         if direction == 'UP':
#             distance = -distance
#         return self.send('G1 X{:.4f} F{:d}'.format(distance, abs(speed)))

#     def moveZ(self, direction, distance, speed):
#         """Move build platform up/down a certain distance at a
#         given speed.

#         :param str direction: can only be 'UP' or 'DOWN'
#         :param distance: distance in millimeters.
#         :param speed: Always treated as positive. The unit is mm/min.
#         """
#         if direction == 'UP':
#             distance = -distance

#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("moveZ start: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))
#         self.load_cell_file.write("moveZ start: %f \r\n" %(self.getTimeRelative()))
#         value = self.send('G1 Z{:.4f} F{:d}'.format(distance, abs(speed)))

#         encoder_counts = self.encoder.readEncoder()
#         self.encoder_print_file.write("moveZ end: %d, %f \r\n" %(encoder_counts, self.encoder_counts_to_mm(encoder_counts)))
#         self.load_cell_file.write("moveZ end: %f \r\n" %(self.getTimeRelative()))
#         return value

#     def queryPosition(self):
#         # query position and capture response
#         if self.verbose: print('Sent: ' + '?')
#         return self.transmit('?')

#     def send(self, cmd):
#         # send the command to grbl
#         if self.verbose: print('Sent: ' + cmd)
#         response = self.transmit(cmd)
#         if self.verbose: print("Response: ", response)

#         # send a G4 P0 command to wait for completion of previous command
#         self.transmit('G4 P0')

#         # print current position if in verbose mode
#         if self.verbose: print("position: ", self.queryPosition())

#         # return the reponse of the first command
#         return response

#     def transmit(self, cmd):
#         self.write(bytes(cmd + '\r', encoding='ascii')) # write to serial tx buffer
#         return self.receive()                           # wait for response from serial rx buffer

#     def receive(self):
#         response = b''
#         response += self.readline()     # wait for the first line to fill in the rx buffer
#         while self.in_waiting:          # while there is more data in the rx buffer
#             response += self.readline() # read next line from rx buffer
#         return response.decode()        # return decoded byte response (as string)

#     def encoder_counts_to_mm(self, counts):
#         num_revolutions = counts / self.encoder_counts_per_revolution
#         num_mm = num_revolutions * self.lead_screw_pitch_mm
#         return num_mm

#     def __del__(self):
#         try:
#             self.goToZmax()
#             self.close()
#         except serial.serialutil.SerialException:
#             pass

# def findUsbPort(hwid):
#     ports = list(serial.tools.list_ports.comports())
#     for p in ports:
#             if 'ttyUSB' in p.name:
#                 print("Found", p.device)
#                 if p.location == '1-1.2':
#                     return p.device

# def findACMport(hwid):
#     ports = list(serial.tools.list_ports.comports())
#     for p in ports:
#             if 'ttyACM' in p.name:
#                 print("Found", p.device)
#                 if hwid in p.hwid:
#                     return p.device

# def solusTest():
#     s = Solus('1A86:7523')
#     print("CONNECT")
#     s.connect()
#     print("INITIALIZE")
#     s.initialize()
#     print("GO TO Z MIN")
#     s.goToZmin()
#     print("GO TO Z MAX")
#     s.goToZmax()

#     commandChain= [
#           "WAIT 0.1",
#           "BP UP 1 SPEED 300",
#           "QW DOWN 3 SPEED 300",
#           "WAIT 1.5",
#           "BP UP 2 SPEED 300",
#           "QW UP 3 SPEED 300",
#           "BP DOWN 3 SPEED 300",
#           "WAIT 1.5"
#         ]

#     print("GO TO 1mm")
#     s.goToFirstLayerHeight(0.1)

#     print(commandChain)
#     for i in range(0,5):
#         print("Layer", i)
#         s.printCycle(.01, commandChain)

#     print("DONE")


# def encoderTest():
#     encoder = Encoder(encoder_HWID)
#     encoder.connect()
#     print(encoder.readEncoder())
#     encoder.close()


# if __name__ == '__main__':
#     encoderTest()
#     print("Done")
