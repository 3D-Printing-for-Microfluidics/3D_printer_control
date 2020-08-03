import time
import atexit
from struct import pack, unpack
import serial
import serial.tools.list_ports

# helper function to find handle to K-Cube
def find_device():
    x = serial.tools.list_ports.comports()
    for device in x:
        if "K-Cube" in device.description:
            print("Found {}".format(device))
            return device.device
    return None  # stage not found


class KDC101:
    # Port Settings
    baud_rate = 115200
    data_bits = 8
    stop_bits = 1
    Parity = serial.PARITY_NONE
    Channel = 1  # channel is always 1 for a K Cube/T Cube
    Device_Unit_SF = 34304.0  # pg 34 of protocol PDF (as of Issue 23)
    destination = 0x50  # destination byte; 0x50 for T Cube/K Cube, USB controllers
    source = 0x01  # source Byte
    maxPos = 25.0
    minPos = 0.0
    relativeMode = True

    def __init__(self, defaultPos=0):
        # Controller's Port and Channel
        self.port = find_device()
        if self.port is None:
            raise ValueError("Thor Labs stage not found")
        self.defaultPos = defaultPos
        self.KDC101 = serial.Serial(
            port=self.port,
            baudrate=self.baud_rate,
            bytesize=self.data_bits,
            parity=self.Parity,
            stopbits=self.stop_bits,
            timeout=0.1,
        )
        self.getHardwareInfo()
        self.enableStage(enable=True)
        self.homed = False
        # the stage only returns a number other than 0 if it is already homed
        if self.getCurrentPos() != 0:
            self.homed = True
        atexit.register(self.KDC101.close)
        atexit.register(self.enableStage, enable=False)

    def home(self):
        # Home Stage; MGMSG_MOT_MOVE_HOME
        self.KDC101.write(
            pack("<HBBBB", 0x0443, self.Channel, 0x00, self.destination, self.source)
        )
        print("Homing stage...")

        # Confirm stage homed before advancing; MGMSG_MOT_MOVE_HOMED
        Rx = ""
        Homed = pack("<H", 0x0444)
        # we do this with number of attempts as it might otherwise freeze here (300 attempts = ~25 sec)
        # if it freezes, we just home again
        attempts = 0
        while Rx != Homed and not self.homed:
            if attempts > 300:
                print("Homing Failed: Trying again")
                self.KDC101.write(
                    pack(
                        "<HBBBB",
                        0x0443,
                        self.Channel,
                        0x00,
                        self.destination,
                        self.source,
                    )
                )
                attempts = 0
            Rx = self.KDC101.read(2)
            attempts = attempts + 1

        self.homed = True
        print("Stage Homed")
        self.flushUSB()

    def move(self, pos, microns=True, relative=True):

        # update positioning mode
        if relative:
            self.setRelative()
        else:
            self.setAbsolute()

        if microns:
            position = pos * 1e-3  # translate into um
        else:
            position = pos

        if self.relativeMode:
            # Move to absolute position in mm; MGMSG_MOT_MOVE_ABSOLUTE (long version)
            # currPos = self.getCurrentPos()
            dUnitpos = int(self.Device_Unit_SF * position)
            code = 0x0448

            # if currPos returns as 'undef' we don't know the position of the stage.
            # So the movement may work or it might not.
            # Best practice is to home after every initialization.
            # Matthew - 10/4/19 - this doesn't appear to have been tested well, removing it for now
            # if not isinstance(currPos, str):
            #     if self.minPos > currPos + position <= self.maxPos:
            #         print("It's false: currPos: {} pos: {}".format(currPos, position))
            #         return False
        elif abs(position) < 25:
            dUnitpos = int(self.Device_Unit_SF * abs(position))
            code = 0x0453
        else:
            return False

        # we do this recursively otherwise it might freeze here (each ittr = ~10 sec)
        # if it freezes, we just home again
        self.KDC101.write(
            pack(
                "<HBBBBHi",
                code,
                0x06,
                0x00,
                self.destination | 0x80,
                self.source,
                self.Channel,
                dUnitpos,
            )
        )
        print("Moving stage", pos, "...")
        finished_succeccfully = self.confirmMoveFinished()
        if not finished_succeccfully:
            self.move(0)
        return True

    def setRelative(self):
        self.relativeMode = True

    def setAbsolute(self):
        self.relativeMode = False

    def confirmMoveFinished(self):
        # Confirm stage completed move before advancing; MGMSG_MOT_MOVE_COMPLETED
        Rx = ""
        Moved = pack("<H", 0x0464)
        attempts = 0
        while Rx != Moved:
            if attempts > 100:
                print("Move Failed: Trying again")
                return False
            Rx = self.KDC101.read(2)
            attempts = attempts + 1

        print("Move Complete")
        self.flushUSB()
        return True

    def initialize(self):
        # Create Serial Object
        self.getHardwareInfo()
        self.enableStage(enable=True)

    def sendServerAlive(self):
        self.KDC101.write(
            pack("<HBBBB", 0x0492, 0x00, 0x00, self.destination, self.source)
        )

    def getHardwareInfo(self):
        # Get HW info; MGMSG_HW_REQ_INFO; may be require by a K Cube to allow confirmation Rx messages
        self.KDC101.write(pack("<HBBBB", 0x0005, 0x00, 0x00, 0x50, 0x01))
        self.flushUSB()

    def enableStage(self, enable=True):
        # Enable Stage; MGMSG_MOD_SET_CHANENABLESTATE
        state = 0x01 if enable else 0x02
        self.KDC101.write(
            pack("<HBBBB", 0x0210, self.Channel, state, self.destination, self.source)
        )
        time.sleep(0.1)

    def flushUSB(self):
        self.KDC101.flushInput()
        self.KDC101.flushOutput()

    def getCurrentPos(self):
        # for some reason sometimes the first one fails.
        # if it is startup, the first 2 fail
        # so we get it twice
        self.getCurrentPosHelper()
        self.getCurrentPosHelper()
        return self.getCurrentPosHelper()

    def getCurrentPosHelper(self):
        # Request Position; MGMSG_MOT_REQ_POSCOUNTER
        self.KDC101.write(
            pack("<HBBBB", 0x0411, self.Channel, 0x00, self.destination, self.source)
        )

        # Read back position returns by the cube; Rx message MGMSG_MOT_GET_POSCOUNTER
        _, _, position_dUnits = unpack(
            "<6sHI", self.KDC101.read(12)
        )  # first two returns are header and chan_dent
        getpos = position_dUnits / float(self.Device_Unit_SF)

        if int(getpos) == 33400:
            return "undef"

        if int(getpos) == 125203:
            getpos = 0.0

        getpos = round(
            getpos * 1000, 1
        )  # convert to microns and round to 1 decimal place
        self.flushUSB()  # added to test if it fixes the read error

        if not self.homed and getpos == 0.0:
            return "undef"

        return getpos


if __name__ == "__main__":
    kc = KDC101()
    print(kc.getCurrentPos())
    kc.home()

    for _ in range(2):
        print(kc.getCurrentPos())
        kc.move(1000)
        print(kc.getCurrentPos())
        kc.move(-1000)

    kc.move(10000)
    print(kc.getCurrentPos())
