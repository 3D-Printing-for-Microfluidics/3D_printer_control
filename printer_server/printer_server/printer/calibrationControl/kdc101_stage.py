from struct import pack,unpack 
import serial
import time
from apscheduler.schedulers.background import BackgroundScheduler

if __name__ == "__main__":
    from calibrationStage import CalibrationStage
else:
    from .calibrationStage import CalibrationStage

import serial.tools.list_ports

class KDC101(CalibrationStage):
    #Port Settings
    baud_rate = 115200
    data_bits = 8
    stop_bits = 1
    Parity = serial.PARITY_NONE
    Channel = 1 #Channel is always 1 for a K Cube/T Cube
    Device_Unit_SF = 34304. #pg 34 of protocal PDF (as of Issue 23)
    destination = 0x50 #Destination byte; 0x50 for T Cube/K Cube, USB controllers
    source = 0x01 #Source Byte
    maxPos = 25.0
    minPos = 0.0
    relativeMode = True

    def __init__(self, defaultPos=0):
        #Controller's Port and Channel
        self.USB_Device = self.getUSBDevice()
        self.defaultPos = defaultPos
        # print(self.USB_Device)

    def __del__(self):
        try:
            self.enableStage(enable=False)
            self.scheduler.shutdown(wait=False)
            self.KDC101.close()
        except:
            pass


    def home(self):
        #Home Stage; MGMSG_MOT_MOVE_HOME 
        self.KDC101.write(pack('<HBBBB', 0x0443, self.Channel, 0x00, self.destination, self.source))
        print('Homing stage...')

        #Confirm stage homed before advancing; MGMSG_MOT_MOVE_HOMED 
        Rx = ''
        Homed = pack('<H',0x0444)
        while Rx != Homed:
            Rx = self.KDC101.read(2)

        print('Stage Homed')
        self.flushUSB()

    def move(self, pos, microns=True):
        if microns:
            position = pos * 1e-3 # translate into um
        else:
            position = pos
        if self.relativeMode:
            #Move to absolute position in mm; MGMSG_MOT_MOVE_ABSOLUTE (long version)
            currPos = self.getCurrentPos()
            dUnitpos = int(self.Device_Unit_SF*position)
            code = 0x0448

            # if currPos returns as 'undef' we don't know the position of the stage. 
            # So the movement may work or it might not. 
            # Best practice is to home after every initialization.
            if not isinstance(currPos, str):
                if self.minPos > currPos + position <= self.maxPos:
                    print("It's false: currPos: {} pos: {}".format(currPos, position))
                    return False
        elif abs(position) < 25:
            dUnitpos = int(self.Device_Unit_SF*abs(position))
            code = 0x0453
        else: 
            return False

        self.KDC101.write(pack('<HBBBBHi', code, 0x06, 0x00, self.destination|0x80, self.source, self.Channel, dUnitpos))
        print('Moving stage')
        self.confirmMoveFinished()
        return True
            
    def setRelative(self):
        self.relativeMode = True

    def setAbsolute(self):
        self.relativeMode = False

    def confirmMoveFinished(self):
        #Confirm stage completed move before advancing; MGMSG_MOT_MOVE_COMPLETED 
        Rx = ''
        Moved = pack('<H',0x0464)
        while Rx != Moved:
            Rx = self.KDC101.read(2)
        
        print('Move Complete')
        self.flushUSB()

    def initialize(self):
        #Create Serial Object
        self.KDC101 = serial.Serial(port = self.USB_Device, 
                                    baudrate = self.baud_rate, 
                                    bytesize = self.data_bits, 
                                    parity = self.Parity, 
                                    stopbits = self.stop_bits,
                                    timeout = 0.1)

        self.getHardwareInfo()
        self.enableStage(enable=True)

        # set up the heartbeat messgaes
        self.scheduler = BackgroundScheduler()
        self.serverAliveJob = self.scheduler.add_job(self.sendServerAlive, 'interval', seconds=.9)
        self.scheduler.start()

    def sendServerAlive(self):
        self.KDC101.write(pack('<HBBBB', 0x0492, 0x00, 0x00, self.destination, self.source))

    def getHardwareInfo(self):
        #Get HW info; MGMSG_HW_REQ_INFO; may be require by a K Cube to allow confirmation Rx messages
        self.KDC101.write(pack('<HBBBB', 0x0005, 0x00, 0x00, 0x50, 0x01))
        self.flushUSB()

    def enableStage(self, enable=True):
        #Enable Stage; MGMSG_MOD_SET_CHANENABLESTATE 
        state = 0x01 if enable else 0x02
        self.KDC101.write(pack('<HBBBB', 0x0210, self.Channel, state, self.destination, self.source))
        time.sleep(0.1) 


    def getUSBDevice(self):
	    # prints available devices
        x = serial.tools.list_ports.comports()
        for device in range(len(x)):
            if "K-Cube" in x[device].product:
                return x[device].device
 
    def flushUSB(self):
        self.KDC101.flushInput()
        self.KDC101.flushOutput()

    def getCurrentPos(self):
        #Request Position; MGMSG_MOT_REQ_POSCOUNTER
        self.KDC101.write(pack('<HBBBB', 0x0411, self.Channel, 0x00, self.destination, self.source))

        #Read back position returns by the cube; Rx message MGMSG_MOT_GET_POSCOUNTER 
        header, chan_dent, position_dUnits = unpack('<6sHI', self.KDC101.read(12))
        # import pdb; pdb.set_trace()
        getpos = position_dUnits/float(self.Device_Unit_SF)
        if int(getpos) == 125203:
            getpos = 0.0
        elif int(getpos) == 33400:
            getpos = 'undef'
        return getpos

if __name__ == "__main__":
    kc = KDC101()
    kc.initialize()
    kc.getCurrentPos()
    kc.home()
    # kc.moveAbsoluePos(15)
    # kc.moveRelativePos(-25)
    # kc.moveRelativePos(5)
    kc.getCurrentPos()
    kc.move(50)
    kc.getCurrentPos()
    kc.move(0)
    kc.getCurrentPos()