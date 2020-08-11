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
    def __init__(self):
        self.homed = False
        self.Device_Unit_SF = 34304.0  # pg 34 of protocol PDF (as of Issue 23)
        self.Channel = 1
        self.destination = 0x50
        self.source = 0x01
        self.maxPos = 25.0
        self.minPos = 0.0
        self.relativeMode = True
        self.port = None
        self.serial_handle = None

    def connect(self):
        self.port = find_device()
        if self.port is None:
            raise ValueError("Thor Labs stage not found")
        self.serial_handle = serial.Serial(
            port=self.port,
            baudrate=115200,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=0.1,
        )
        self.getHardwareInfo()
        self.enableStage(enable=True)
        atexit.register(self.serial_handle.close)
        atexit.register(self.enableStage, enable=False)

    def home(self):
        # Home Stage; MGMSG_MOT_MOVE_HOME
        self.serial_handle.write(
            pack("<HBBBB", 0x0443, self.Channel, 0x00, self.destination, self.source)
        )
        print("Homing stage...")

        # Confirm stage homed before advancing; MGMSG_MOT_MOVE_HOMED
        Rx = ""
        Homed = pack("<H", 0x0444)
        # we do this with number of attempts as it might otherwise freeze here
        # (300 attempts = ~25 sec) if it freezes, we just home again
        attempts = 0
        while Rx != Homed and not self.homed:
            if attempts > 300:
                print("Homing Failed: Trying again")
                self.serial_handle.write(
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
            Rx = self.serial_handle.read(2)
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
        self.serial_handle.write(
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
            Rx = self.serial_handle.read(2)
            attempts = attempts + 1

        print("Move Complete")
        self.flushUSB()
        return True

    def sendServerAlive(self):
        self.serial_handle.write(
            pack("<HBBBB", 0x0492, 0x00, 0x00, self.destination, self.source)
        )

    def getHardwareInfo(self):
        # Get HW info; MGMSG_HW_REQ_INFO; may be require by a K Cube to
        #  allow confirmation Rx messages
        self.serial_handle.write(pack("<HBBBB", 0x0005, 0x00, 0x00, 0x50, 0x01))
        self.flushUSB()

    def enableStage(self, enable=True):
        # Enable Stage; MGMSG_MOD_SET_CHANENABLESTATE
        state = 0x01 if enable else 0x02
        self.serial_handle.write(
            pack("<HBBBB", 0x0210, self.Channel, state, self.destination, self.source)
        )
        time.sleep(0.1)

    def flushUSB(self):
        self.serial_handle.flushInput()
        self.serial_handle.flushOutput()

    def getCurrentPos(self):
        # for some reason sometimes the first one fails.
        # if it is startup, the first 2 fail
        # so we get it twice
        self.getCurrentPosHelper()
        self.getCurrentPosHelper()
        return self.getCurrentPosHelper()

    def getCurrentPosHelper(self):
        # Request Position; MGMSG_MOT_REQ_POSCOUNTER
        self.serial_handle.write(
            pack("<HBBBB", 0x0411, self.Channel, 0x00, self.destination, self.source)
        )

        # Read back position returns by the cube; Rx message MGMSG_MOT_GET_POSCOUNTER
        _, _, position_dUnits = unpack(
            "<6sHI", self.serial_handle.read(12)
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
