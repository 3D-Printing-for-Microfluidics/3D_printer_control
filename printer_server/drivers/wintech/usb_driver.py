"""Wintech USB driver"""

import sys
import time
import logging
import usb.core
import usb.util


def numToBits(number, length):
    """Convert a number into a bit string of given length.
    number - number to convert
    length - length of resultant bit string
    """
    b = bin(number)[2:]
    padding = length - len(b)
    b = "0" * padding + b
    return b


def bitsToBytes(bitString):
    """Convert a bit string into a list of full bytes."""
    bytelist = []
    if len(bitString) % 8 != 0:  # add 0 padding to fill last byte
        padding = 8 - len(bitString) % 8
        bitString = "0" * padding + bitString
    for i in range(len(bitString) // 8):  # pack bytes
        bytelist.append(int(bitString[8 * i : 8 * (i + 1)], 2))
    bytelist.reverse()
    return bytelist


# Controller class
class WintechUSB:
    """USB interface for Wintech optical engine utilizing the TI DLPC900
    controller.
    """

    def __init__(self, log_level=logging.DEBUG):
        """Initialize a WintechUSB object.

        dev - handle to kernel driver
        ans - response buffer
        transactionCounter - a counter used for the sequence byte
        isIdle - track the idle state of the DMD
        """
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.dev = None  # start with no device connected
        self.ans = []  # empty response buffer
        self.transactionCounter = 0  # counter for sequence byte
        self.isIdle = False  # keeps track of idle state of dmd

    def connect(self, quick=False):
        """Finds and connect to the device and perform other setup.

        First looks for the VID and PID combination representing the
        DLPC900 controller. Next frees the USB driver and sets the
        configuration. If quick is False, also sets up the sequencer,
        video mode, and input source.
        """
        self.log.info("Connecting to DLPC900 via USB...")
        self.dev = usb.core.find(idVendor=0x0451, idProduct=0xC900)
        if self.dev is None:
            sys.exit("DLPC900 not found. Is it connected and turned on?")
            return
        self.freeDriver(self.dev)
        self.dev.set_configuration()

        if not quick:
            self.stopSequence()
            self.setDisplayMode(2)
            self.selectInputSource(1)

    def freeDriver(self, device):
        """Free the USB driver if it is already in use."""
        self.log.debug("Freeing device driver...")
        for cfg in device:
            for intf in cfg:
                n = intf.bInterfaceNumber
                if device.is_kernel_driver_active(n):
                    try:
                        device.detach_kernel_driver(n)
                    except usb.core.USBError as e:
                        sys.exit(f"Couldn't detach kernel driver from interface {n}: {e}")

    def setDisplayMode(self, mode):
        """Set the display mode. This takes about 5 seconds.

        mode:
            0 = Video mode
            1 = Pre-stored pattern mode (Images from flash)
            2 = Video pattern mode
            3 = Pattern On-The-Fly mode (Images loaded through USB/I2C)
        """
        displayModes = [
            "Video mode",
            "Pre-stored pattern mode",
            "Video pattern mode",
            "Pattern On-The-Fly mode",
        ]
        self.log.debug("Set display mode to: %s", displayModes[mode])
        if mode < 0 or mode > 3:
            sys.exit("Bad display mode value passed in to setDisplayMode()")
            return
        self.send("w", 0x1A1B, [mode])
        time.sleep(5)
        self.checkAllStatus()

    def selectInputSource(self, source):
        """Select an input source. See IT6535 Power Mode Command for
        more details. It takes about 6 seconds to power up the IT6535
        receiver.

        source:
            0 = Power-Down (Outputs will be tri-stated).
            1 = Power-Up for HDMI input.
            2 = Power-Up for DisplayPort input.
        """
        IT6535_power_modes = ["Power-down", "HDMI", "DisplayPort"]
        self.log.debug("IT6535 power mode set to: %s", IT6535_power_modes[source])
        if source < 0 or source > 2:
            sys.exit("Bad source value passed in to selectInputSource()")
        self.send("w", 0x1A01, [source])
        time.sleep(6)
        self.checkAllStatus()

    def send(self, mode, command, data=None, sequenceByte=0x0):
        """Send a command to the DLPC900 controller over USB.

        See 1.2.1 "USB Transaction Sequence" in the DLPC900 programmer's
        guide for more information.
        mode: 'r' or 'w'
        sequenceByte: The sequence byte is used primarily when the host
            wants a response from the DLPC900. The DLPC900 will respond
            with the same sequence byte that the host sent. The host can
            then match the sequence byte from the command it sent with
            the sequence byte from the DLPC900 response to know which
            command the response applies to.
        command: The two byte usb command specified in the programmer's
            guide.
        data: The rest of the parameters the command needs. See the
            programmer's guide for specific details.
        """
        if data is None:
            data = []

        # format header
        buffer = []
        flagByte = "11000000" if mode == "r" else "01000000"
        buffer.append(bitsToBytes(flagByte)[0])
        if sequenceByte == 0x0:
            sequenceByte = self.transactionCounter & 0xFF
        buffer.append(sequenceByte)

        # calculate the payload length (data +2 bytes for USB command)
        pLength = bitsToBytes(numToBits(len(data) + 2, 16))
        buffer.append(pLength[0])  # add LSB then MSB
        buffer.append(pLength[1])

        # format USB command - LSB first, then MSB
        buffer.append(command & 0xFF)
        buffer.append(command >> 8)

        # format data and send in 64 byte packets
        if len(buffer) + len(data) < 65:
            for i in data:
                buffer.append(i)
            for i in range(64 - len(buffer)):
                buffer.append(0x00)  # pad unused space with zeroes
            self.write(buffer)
        else:  # command will not fit into one transaction
            for i in range(64 - len(buffer)):
                buffer.append(data[i])
            self.write(buffer)  # write first 64 bytes
            buffer = []  # clear the buffer
            j = 0
            while j < len(data) - 58:  # set up buffer in 64 byte increments
                buffer.append(data[j + 58])
                j = j + 1
                if j % 64 == 0:
                    self.write(buffer)  # write next 64 bytes
                    buffer = []
            if j % 64 != 0:
                while j % 64 != 0:
                    buffer.append(0x00)  # zero pad last set of bytes up to 64
                    j = j + 1
                self.write(buffer)  # write final 64 bytes
        self.ans = self.read()
        self.transactionCounter += 1

    def read(self, numBytes=64, endpoint=0x81):
        """Read numBytes bytes from specified endpoint. Should only be
        used directly in send().

        endpoint: endpoint to read from. The default IN endpoint for the
            DLPC900 is 0x81.
        numBytes: the number of bytes to read. The maximum at once for
            the DLPC900 is 64.
        """
        data = self.dev.read(endpoint, numBytes)
        # if self.veryVerbose:
        self.log.debug("READ endpoint %s:%s", hex(endpoint), self.decodeResponse(data))
        return data

    def write(self, data=None, endpoint=0x1):
        """Write the provided data to the specified endpoint. Should
        only be used directly in send().

        data: The data to write.
        endpoint: The endpoint to write to. The default OUT endpoint for
            the DLPC900 is 0x1.
        """
        # if self.veryVerbose:
        self.log.debug("WRITE endpoint %s:%s", hex(endpoint), self.decodeResponse(data))
        self.dev.write(endpoint, data, timeout=10000)

    def checkHardwareStatus(self):
        """Read hardware status. See 2.1.1 "Hardware Status" in the
        programmer's guide.
        """
        # if self.veryVerbose:
        self.log.debug("Checking hardware status...")
        self.send("r", 0x1A0A)
        response = hex(self.ans[4])
        self.log.debug("     Hardware status:\t%s", response)
        return response

    def checkSystemStatus(self):
        """Read system status. See 2.1.2 "System Status" in the
        programmer's guide.
        """
        # if self.veryVerbose:
        self.log.debug("Checking system status...")
        self.send("r", 0x1A0B)
        response = hex(self.ans[4])
        self.log.debug("     System status:\t%s", response)
        return response

    def checkMainStatus(self):
        """Read main status. See 2.1.3 "Main Status" in the programmer's
        guide.
        """
        # if self.veryVerbose:
        self.log.debug("Checking main status...")
        self.send("r", 0x1A0C)
        response = hex(self.ans[4])
        self.log.debug("     Main status:\t%s", response)
        return response

    def checkErrorStatus(self):
        """Read error status. See 2.1.6 "Read Error Code" in the
        programmer's guide.
        """
        # if self.veryVerbose:
        self.log.debug("Checking for errors...")
        self.send("r", 0x0100)
        response = hex(self.ans[4])
        self.log.debug("     Error status:\t%s", response)
        return response

    def checkAllStatus(self):
        """Read all status."""
        hwStat = self.checkHardwareStatus()
        sysStat = self.checkSystemStatus()
        mainStat = self.checkMainStatus()
        errorStat = self.checkErrorStatus()
        print("     Status: ", hwStat, sysStat, mainStat, errorStat)

    def setLedPower(self, power):
        """Set the current supplied to the LED driver. See 2.3.5.2 "LED
        Driver Current" in the programmer's guide.

        CAUTION: Care should be taken when using this command. Improper
        use of this command can lead to damage to the system. The
        setting of the LED current depends on many system and
        application parameters (including projector thermal design, LED
        specifications, selected display mode, and so forth). Therefore,
        recommended and absolute-maximum settings vary greatly.

        This parameter controls the pulse duration of the specific LED
        PWM modulation output pin. The resolution is 8 bits and
        corresponds to a percentage of the LED current. The PWM value
        can be set from 0 to 100% in 256 steps. If the LED PWM polarity
        is set to normal polarity, a setting of 0xFF gives the maximum
        PWM current. The LED current is a function of the specific LED
        driver design.

        Our system shipped with a default value of 0x64 which is 100/256
        or 39% max power. To be safe, I am leaving this as the maximum.
        """
        self.log.info("Setting LED power to %s", power)
        if power < 0 or power > 100:
            sys.exit()
        self.send("w", 0x0B01, [0, 0, power])
        self.checkAllStatus()

    def ledOn(self):
        """Turn on the LED. See 2.3.5.1 "LED Enable Outputs" in the
        programmer's guide.
        """
        self.log.info("LED turned on")
        self.send("w", 0x1A07, [0x4])
        self.checkAllStatus()

    def ledOff(self):
        """Turn off the LED. See 2.3.5.1 "LED Enable Outputs" in the
        programmer's guide.
        """
        self.log.info("LED turned off")
        self.send("w", 0x1A07, [0x0])
        self.checkAllStatus()

    def ledFromSequencer(self):
        """Set the LED to be controlled by the sequencer. See 2.3.5.1
        "LED Enable Outputs" in the programmer's guide.
        """
        self.log.debug("LED set to run from sequencer")
        self.send("w", 0x1A07, [0x8])
        self.checkAllStatus()

    def idleOn(self):
        """Enable idle mode. - See section 2.4.1.4 "DMD Idle Mode" in
        the programmer's guide.

        "It is strongly recommended that anytime the DMD is idle and not
        actively projecting data that the DMD Idle Mode be enabled to
        assist in maximizing DMD lifetime. For example, whenever the
        system is idle, between exposures if the application allows for
        it, or when the exposure pattern sequence is stopped. To enable
        this mode, the pattern sequences must first be stopped.
        To restart the pattern sequence, this mode must be disabled."
        """
        if not self.isIdle:
            self.log.debug("Idle mode enabled")
            self.isIdle = True
            self.send("w", 0x0201, [0x1])
            self.checkAllStatus()

    def idleOff(self):
        """Enable idle mode. - See section 2.4.1.4 "DMD Idle Mode" in
        the programmer's guide."""
        if self.isIdle:
            self.log.debug("Idle mode disabled")
            self.isIdle = False
            self.send("w", 0x0201, [0x0])
            self.checkAllStatus()

    def standby(self):
        """Put DLPC900 into standby power mode - See 2.3.1.1 "Power
        Mode" in the programmer's guide.

        "The Power Control places the DLPC900 in a standby state and
        powers down the DMD interface. Enter Standby mode prior to any
        planned system power shutdowns to help prolong DMD lifetime.
        Standby mode should only be enabled after all data for the last
        frame to be displayed has been transferred to the DLPC900.
        Standby mode must be disabled prior to sending any new data."
        Status commands still work in idle mode.
        """
        self.send("w", 0x0200, [0x1])
        self.checkAllStatus()

    def wakeUp(self):
        """Put DLPC900 into normal power mode. See 2.3.1.1 "Power Mode"
        in the programmer's guide.
        """
        self.send("w", 0x0200, [0x0])
        self.checkAllStatus()

    def softwareReset(self):
        """Reset the internal DLPC900 software. A full reset takes about
        7 seconds.
        """
        self.send("w", 0x0200, [0x2])
        time.sleep(7)
        self.checkAllStatus()

    def startSequence(self):
        """Start the pattern display sequence. See 2.4.4.3.1 "Pattern
        Display Start/Stop" in the programmer's guide.
        """
        self.log.info("Starting sequence...")
        self.send("w", 0x1A24, [0x2])
        self.checkAllStatus()

    def pauseSequence(self):
        """Pause the pattern display sequence. See 2.4.4.3.1 "Pattern
        Display Start/Stop" in the programmer's guide.

        If a pattern is paused during exposure, the next start command
        will start the pattern sequence by re-displaying the current
        pattern in the sequence from the beginning.
        """
        self.log.info("Pausing sequence...")
        self.send("w", 0x1A24, [0x1])
        self.checkAllStatus()

    def stopSequence(self):
        """Stop the pattern display sequence. See 2.4.4.3.1 "Pattern
        Display Start/Stop" in the programmer's guide.

        If a pattern is stopped during exposure, the next start command
        will start the pattern sequence by re-displaying the current
        pattern in the sequence from the beginning.
        """
        self.log.info("Stopping sequence...")
        self.send("w", 0x1A24, [0x0])
        self.checkAllStatus()

    def configurePatternLut(self, images=1, repeat=1):
        """Configure the pattern LUT. This must be called before
        defining any patterns. See 2.4.4.3.3 "Pattern Display LUT
        Configuration" in the programmer's guide.

        images - The number of patterns to be uploaded.
        repeat - The number of times to repeat each pattern. Defaults to
            1, 0 means repeat forever.
        """
        if images < 1:
            sys.exit("Bad number of images provided to configurePatternLut()")
        if repeat < 0:
            sys.exit("Bad repeat number provided to configurePatternLut()")
        self.log.debug("Configuring Pattern LUT...")
        payload = bitsToBytes(numToBits(repeat, 32) + "00000" + numToBits(images, 11))
        self.send("w", 0x1A31, payload)
        self.checkAllStatus()

    def definePattern(self, exposure):
        """Define a pattern. See 2.4.4.3.4 "Pattern Display LUT
        Definition" in the programmer's guide. The sequencer must be
        stopped before defining a new pattern.

        exposure - Exposure time in ms.

        The minimum exposure time varies with bit depth. Allowable
        exposure times can be read with the command 0x1a42. See 2.3.5.4
        "Get Minimum LED Pattern Exposure" in the programmer's guide.
        The minimums for this system are as follows:
        bit depth:     1    2    3    4    5     6     7     8
        min exposure: 105  304  394  823  1215  1487  1998  4046

        This is the payload format:

        12 bytes total
        Bytes 0-1: Pattern index (valid range 0 - 511).
        Bytes 2-4: Exposure time (bits 31:24 are reserved, bits 23:0 are
            the exposure time in microseconds)
        Byte 5: Bit 0 - clear the pattern after exposure. This is only
            applicable for 1 bit patterns with an external trigger. For
            other patterns, the clear is automatically handled.
            Bits 1-3: Image bit depth. b000 = 1, b001 = 2,... b111 = 8.
            Bits 5-6: Color. In the Wintech, the LED is on the blue
            channel. b000 = All LEDs disabled, b001 = Red, b010 = Green,
            b011 = Yellow (Green + Red), b100 = Blue,
            b101 = Magenta (Blue + Red), b110 = Cyan (Blue + Green),
            b111 = White (Blue + Green + Red)
            Bit 7: Trigger/VSYNC. 1 = Wait for trigger before displaying
            the pattern, 0 = Continue running after previous pattern.
        Bytes 6-8: dark wait time (bits 31:24 - reserved, bits 23:0 -
            dark display time following the exposure (in microseconds))
        Byte 9: Trigger 2. Bit 0 - trigger 2 setting (1 = Disable
            trigger 2 output for this pattern 0 = Enable trigger 2
            output for this pattern). Bits 1:7 - reserved.
        Bytes 10-11: Image pattern settings. Bits 10:0 - Image pattern
            index (Not applicable in video pattern mode) Valid Range
            0-255. Bits 115:11 - Bit position in the image pattern
            (Frame in video pattern mode). Valid range 0-23.
        """
        self.log.debug("Defining pattern...")
        self.stopSequence()
        index = 0
        bitDepth = 8
        color = "100"  # blue channel
        triggerIn = 1
        darkTime = 0
        triggerOut = 0
        patternId = 0
        bitPosition = 0
        exposure = int(exposure * 1000)  # convert exposure time to us
        minExposure = [105, 304, 394, 823, 1215, 1487, 1998, 4046]
        if exposure < minExposure[bitDepth - 1]:
            sys.exit("Too small of exposure passed to definePattern()")
        if exposure > 0xFFFFFF:
            sys.exit("Too large of exposure passed to definePattern()")

        payload = list(range(12))
        payload[0] = index & 0xFF
        payload[1] = (index >> 8) & 0xFF
        payload[2] = exposure & 0xFF
        payload[3] = (exposure >> 8) & 0xFF
        payload[4] = (exposure >> 16) & 0xFF
        temp = int("1") & 0x1
        temp |= ((bitDepth - 1) << 1) & 0x0E
        temp |= (int(color) << 4) & 0x70
        temp |= (triggerIn << 7) & 0x80
        payload[5] = int(temp)
        payload[6] = darkTime & 0xFF
        payload[7] = (darkTime >> 8) & 0xFF
        payload[8] = (darkTime >> 16) & 0xFF
        payload[9] = triggerOut
        payload[10] = patternId
        payload[11] = (bitPosition & 0x1F) << 3
        self.send("w", 0x1A34, payload)
        self.checkAllStatus()
