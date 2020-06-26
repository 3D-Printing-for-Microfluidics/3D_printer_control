import time
import atexit
from struct import pack, unpack
import serial
import serial.tools.list_ports

class KDC101_dummy():
    #Port Settings
    baud_rate = 115200
    data_bits = 8
    stop_bits = 1
    Parity = serial.PARITY_NONE
    Channel = 1                     # channel is always 1 for a K Cube/T Cube
    Device_Unit_SF = 34304.         # pg 34 of protocol PDF (as of Issue 23)
    destination = 0x50              # destination byte; 0x50 for T Cube/K Cube, USB controllers
    source = 0x01                   # source Byte
    maxPos = 25.0
    minPos = 0.0
    relativeMode = True

    def __init__(self, defaultPos=0):
        print(" kdc101 - __init({})__".format(defaultPos))

    def home(self):
        print(" kdc101 - home()")

    def move(self, pos, microns=True, fast=False, relative=True):
        print(" kdc101 - move({},{})".format(pos, microns))

    def setRelative(self):
        print(" kdc101 - setRelative()")

    def setAbsolute(self):
        print(" kdc101 - setAbsolute()")

    def confirmMoveFinished(self):
        print(" kdc101 - confirmMoveFinished()")

    def initialize(self):
        print(" kdc101 - initialize()")

    def sendServerAlive(self):
        print(" kdc101 - sendServerAlive()")

    def getHardwareInfo(self):
        print(" kdc101 - getHardwareInfo()")

    def enableStage(self, enable=True):
        print(" kdc101 - enableStage({})".format(enable))

    def getUSBDevice(self):
        print(" kdc101 - getUSBDevice()")

    def flushUSB(self):
        print(" kdc101 - flushUSB()")

    def getCurrentPos(self):
        print(" kdc101 - getCurrentPos()")
