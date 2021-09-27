import sys
import time
import logging
import usb.core
import usb.util

# Convert a number into a bit string of given length
def numToBits(number, length):
    # number - number to convert
    # length - length of resultant bit string

    b = bin(number)[2:]
    padding = length - len(b)
    b = '0' * padding + b
    return b

# Convert a bit string into a list of full bytes
def bitsToBytes(bitString):
    bytelist = []
    if len(bitString) % 8 != 0:                 # add 0 padding to fill last byte
        padding = 8 - len(bitString) % 8
        bitString = '0' * padding + bitString
    for i in range(len(bitString) // 8):        # pack bytes
        bytelist.append(int(bitString[8 *i : 8 *(i + 1)], 2))
    bytelist.reverse()
    return bytelist

# Controller class
class WintechUSB():
    def __init__(self, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.dev = None                         # start with no device connected
        self.ans = []                           # empty response buffer
        self.transactionCounter = 0             # counter for sequence byte
        self.isIdle = False                     # keeps track of idle state of dmd

    # finds and connects to the device and sets up optical engine
    def connect(self, quick=False):
        self.log.info("Connecting to DLPC900 via USB...")
        self.dev = usb.core.find(idVendor=0x0451, idProduct=0xc900)    # find device by VID:PID
        if self.dev is None:
            sys.exit("DLPC900 not found. Is it connected and turned on?")
            return
        self.freeDriver(self.dev)                           # free the USB driver if it is in use
        self.dev.set_configuration()                        # set default USB configuration

        if not quick:
            # set default connection settings
            self.stopSequence()                                 # turn off sequencer before configuration
            self.setDisplayMode(2)                              # set to video pattern mode
            self.selectInputSource(1)                           # select HDMI as input source

    # free up the USB driver if it is already in use
    def freeDriver(self, device):
        self.log.debug("Freeing device driver...")
        # free up usb device
        for cfg in device:
            for intf in cfg:
                if device.is_kernel_driver_active(intf.bInterfaceNumber):
                    try:
                        device.detach_kernel_driver(intf.bInterfaceNumber)
                    except usb.core.USBError as e:
                        sys.exit("Could not detach kernel driver from interface({0}): {1}".format(intf.bInterfaceNumber, str(e)))
                        return

    # set display mode
    def setDisplayMode(self, mode):
        # mode:
        #   0 = Video mode
        #   1 = Pre-stored pattern mode (Images from flash)
        #   2 = Video pattern mode
        #   3 = Pattern On-The-Fly mode (Images loaded through USB/I2C)

        displayModes = ["Video mode", "Pre-stored pattern mode", "Video pattern mode", "Pattern On-The-Fly mode"]
        self.log.debug("Set display mode to: %s", displayModes[mode])
        if mode < 0 or mode > 3:            # reject bad display modes
            sys.exit("Bad display mode value passed in to setDisplayMode()")
            return
        self.send('w', 0x1a1b, [mode])
        time.sleep(5)                       # it takes the DLPC900 about 5 seconds to change display mode
        self.checkAllStatus()

    # power up HDMI (IT6535 Power Mode Command, set to power up HDMI)
    def selectInputSource(self, source):
        #   0 = Power-Down. (Outputs will be tri-stated)
        #   1 = Power-Up for HDMI input.
        #   2 = Power-Up for DisplayPort input.

        IT6535_power_modes = ["Power-down", "HDMI", "DisplayPort"]

        self.log.debug("IT6535 power mode set to: %s", IT6535_power_modes[source])

        if source < 0 or source > 2:    # reject invalid values for source
            sys.exit("Bad source value passed in to selectInputSource()")
            return

        self.send('w', 0x1a01, [source])
        time.sleep(6)                   # it takes the DLPC900 about 6 seconds to power up the IT6535 receiver
        self.checkAllStatus()

    # Send a command over USB to the DLPC900. See 1.2.1 "USB Transaction Sequence" in the DLPC900 programmer's guide
    def send(self, mode, command, data=None, sequenceByte=0x0):
        # mode: 'r' or 'w'
        # sequenceByte: The sequence byte is used primarily when the host wants a response from the
        #               DLPC900. The DLPC900 will respond with the same sequence byte that the host
        #               sent. The host can then match the sequence byte from the command it sent
        #               with the sequence byte from the DLPC900 response
        # command: The two byte usb command specified in the programmer's guide
        # data: The rest of the parameters the command needs. See the programmer's guide for specific details

        # safely set data array to be empty
        if data is None: data = []              # defaulting a parameter to [] is dangerous, so we do this instead

        # format header
        buffer = []
        flagByte = ('11000000' if mode == 'r' else '01000000')  # set flag byte with ternary operator
        buffer.append(bitsToBytes(flagByte)[0])                 # add flag byte to buffer
        if sequenceByte == 0x0:                                 # if no custom sequence byte was supplied
            sequenceByte = (self.transactionCounter & 0xff)     # use transaction count for sequence byte
        buffer.append(sequenceByte)                             # add sequence byte to buffer
        pLength = bitsToBytes(numToBits(len(data) + 2, 16))     # calculate the length of the payload (data +2 bytes for USB command)
        buffer.append(pLength[0])                               # add least significant byte to buffer first
        buffer.append(pLength[1])                               # add most significant byte to buffer

        # format USB command
        buffer.append(command & 0xff)                       # add least significant byte of command to buffer first
        buffer.append(command >> 8)                         # add most significant byte of command to buffer

        # format data and send in 64 byte packets
        if len(buffer) + len(data) < 65:        # command will fit into one transaction (max 64 bytes per transaction)
            for i in data:
                buffer.append(i)                # set up buffer
            for i in range(64-len(buffer)):
                buffer.append(0x00)             # pad unused space with zeroes
            self.write(buffer)
        else:                                   # command will not fit into one transaction
            for i in range(64-len(buffer)):
                buffer.append(data[i])
            self.write(buffer)                  # write first 64 bytes
            buffer = []                         # clear the buffer
            j = 0
            while j < len(data) - 58:           # set up buffer in 64 byte increments
                buffer.append(data[j+58])
                j = j + 1
                if j % 64 == 0:
                    self.write(buffer)          # write next 64 byte increments
                    buffer = []
            if j% 64 != 0:
                while j % 64 != 0:
                    buffer.append(0x00)         # zero pad last set of bytes up to 64
                    j = j + 1
                self.write(buffer)              # write final 64 bytes
        self.ans = self.read()                  # read response
        self.transactionCounter += 1            # increment transaction counter

    # read specified number of bytes from specified endpoint. Should only be used directly in send()
    def read(self, numBytes=64, endpoint=0x81):
        # endpoint: endpoint to read from. The default IN endpoint for the DLPC900 is 0x81
        # numBytes: the number of bytes to read. The maximum at once for the DLPC900 is 64

        data = self.dev.read(endpoint, numBytes)
        # if self.veryVerbose:
        self.log.debug("READ endpoint %s:%s", hex(endpoint), self.decodeResponse(data))
        return data

    # write the provided data to the specified endpoint. Should only be used directly in send()
    def write(self, data=None, endpoint=0x1):
        # data: the data to write
        # endpoint: endpoint to write to. The default OUT endpoint for the DLPC900 is 0x1

        # if self.veryVerbose:
        self.log.debug("WRITE endpoint %s:%s", hex(endpoint), self.decodeResponse(data))
        self.dev.write(endpoint, data, timeout=10000)

    # read hardware status - See 2.1.1 "Hardware Status" in programmer's guide
    def checkHardwareStatus(self):
        # if self.veryVerbose:
        self.log.debug("Checking hardware status...")
        self.send('r', 0x1a0a)
        response = hex(self.ans[4])
        self.log.debug("     Hardware status:\t%s", response)
        return response

    # read system status - See 2.1.2 "System Status" in programmer's guide
    def checkSystemStatus(self):
        # if self.veryVerbose:
        self.log.debug("Checking system status...")
        self.send('r', 0x1a0b)
        response = hex(self.ans[4])
        self.log.debug("     System status:\t%s", response)
        return response

    # read main status - See 2.1.3 "Main Status" in programmer's guide
    def checkMainStatus(self):
        # if self.veryVerbose:
        self.log.debug("Checking main status...")
        self.send('r', 0x1a0c)
        response = hex(self.ans[4])
        self.log.debug("     Main status:\t%s", response)
        return response

    # read error status - See 2.1.6 "Read Error Code" in programmer's guide
    def checkErrorStatus(self):
        # if self.veryVerbose:
        self.log.debug("Checking for errors...")
        self.send('r', 0x0100)
        response = hex(self.ans[4])
        self.log.debug("     Error status:\t%s", response)
        return response

    # convenience function to read all status specified above
    def checkAllStatus(self):
        hwStat = self.checkHardwareStatus()
        sysStat = self.checkSystemStatus()
        mainStat = self.checkMainStatus()
        errorStat = self.checkErrorStatus()
        # print("     Status: ", hwStat, sysStat, mainStat, errorStat)

    # set current to LED driver - See 2.3.5.2 "LED Driver Current" in programmer's guide
    def setLedPower(self, power):
        # CAUTION: Care should be taken when using this command. Improper use of this command can
        # lead to damage to the system. The setting of the LED current depends on many system and
        # application parameters (including projector thermal design, LED specifications, selected
        # display mode, and so forth). Therefore, recommended and absolute-maximum settings vary greatly.
        #
        # This parameter controls the pulse duration of the specific LED PWM modulation output pin.
        # The resolution is 8 bits and corresponds to a percentage of the LED current. The PWM value
        # can be set from 0 to 100% in 256 steps. If the LED PWM polarity is set to normal polarity,
        # a setting of 0xFF gives the maximum PWM current. The LED current is a function of the
        # specific LED driver design.
        #
        # Our system shipped with a default value of 0x64 which is 100/256 or 39% max power. To be safe,
        # I am leaving this as the maximum.

        self.log.info("Setting LED power to %s", power)

        if power < 0 or power > 100:
            sys.exit()
            return      # since sys.exit() can be ignored, ensure this function will exit

        self.send('w', 0x0b01, [0, 0, power])   # update the power. We only use the blue LED
        self.checkAllStatus()

    # turn on the LED - See 2.3.5.1 "LED Enable Outputs" in programmer's guide
    def ledOn(self):
        self.log.info("LED turned on")
        self.send('w', 0x1a07, [0x4])
        self.checkAllStatus()

    # turn off the LED - See 2.3.5.1 "LED Enable Outputs" in programmer's guide
    def ledOff(self):
        self.log.info("LED turned off")
        self.send('w', 0x1a07, [0x0])
        self.checkAllStatus()

    # set LED to be controlled by the sequencer - See 2.3.5.1 "LED Enable Outputs" in programmer's guide
    def ledFromSequencer(self):
        self.log.debug("LED set to run from sequencer")
        self.send('w', 0x1a07, [0x8])
        self.checkAllStatus()

    # decodes a byte list according to the payload length - See 1.2.1 "USB Transaction Sequence" in programmer's guide
    def decodeResponse(self, buffer):
        if len(buffer) < 4:                             # len < 4 means we don't have the header bytes to know how long
            s = ' '.join([hex(i) for i in buffer])      #                  the payload is, so just print what is there
        else:                                           # we have bytes 2 and 3, which tell us how long the payload is
            s = ''
            length = buffer[2] + 0x100 * buffer[3] + 4  # least significant byte of payload length comes first, +4 for header bytes
            for i in range(0, length):
                s = ' '.join((s, hex(buffer[i])))
        return s

    # Idle mode control - See section 2.4.1.4 "DMD Idle Mode" in programmer's guide
    def idleOn(self):
        # "It is strongly recommended that anytime the DMD is idle and not actively
        # projecting data that the DMD Idle Mode be enabled to assist in maximizing
        # DMD lifetime. For example, whenever the system is idle, between exposures
        # if the application allows for it, or when the exposure pattern sequence
        # is stopped. To enable this mode, the pattern sequences must first be
        # stopped. To restart the pattern sequence, this mode must be disabled."

        if not self.isIdle:     # check to see if the dmd is already in idle mode
            self.log.debug("Idle mode enabled")
            self.isIdle = True
            self.send('w', 0x0201, [0x1])
            self.checkAllStatus()
        return

    # Idle mode control - See section 2.4.1.4 "DMD Idle Mode" in programmer's guide
    def idleOff(self):
        if self.isIdle:
            self.log.debug("Idle mode disabled")
            self.isIdle = False
            self.send('w', 0x0201, [0x0])
            self.checkAllStatus()
        return

    # put DLPC900 into standby power mode - See 2.3.1.1 "Power Mode" in programmer's guide
    def standby(self):
        # "The Power Control places the DLPC900 in a standby state and powers down
        # the DMD interface. Enter Standby mode prior to any planned system power
        # shutdowns to help prolong DMD lifetime. Standby mode should only be
        # enabled after all data for the last frame to be displayed has been
        # transferred to the DLPC900. Standby mode must be disabled prior to
        # sending any new data." Status commands still work in idle mode

        self.send('w', 0x0200, [0x1])
        self.checkAllStatus()

    # put DLPC900 into normal power mode - See 2.3.1.1 "Power Mode" in programmer's guide
    def wakeUp(self):
        self.send('w', 0x0200, [0x0])
        self.checkAllStatus()

    # reset the internal DLPC900 software
    def softwareReset(self):
        self.send('w', 0x0200, [0x2])
        time.sleep(7)               # full software reset takes about 7 seconds
        self.checkAllStatus()

    # start the pattern display sequence - See 2.4.4.3.1 "Pattern Display Start/Stop" in the programmer's guide
    def startSequence(self):
        self.log.info("Starting sequence...")
        self.send('w', 0x1a24, [0x2])
        self.checkAllStatus()

    # pause the pattern display sequence - See 2.4.4.3.1 "Pattern Display Start/Stop" in the programmer's guide
    def pauseSequence(self):
        # the next Start command will start the pattern sequence by re-displaying the current pattern in the sequence.
        self.log.info("Pausing sequence...")
        self.send('w', 0x1a24, [0x1])
        self.checkAllStatus()

    # stop the pattern display sequence - See 2.4.4.3.1 "Pattern Display Start/Stop" in the programmer's guide
    def stopSequence(self):
        # the next Start command will restart the pattern sequence from the beginning
        self.log.info("Stopping sequence...")
        self.send('w', 0x1a24, [0x0])
        self.checkAllStatus()

    # must be called before defining patterns - See 2.4.4.3.3 "Pattern Display LUT Configuration" in the programmer's guide
    def configurePatternLut(self, images=1, repeat=1):
        # images - number of patterns to be uploaded
        # repeat - number of times to repeat each pattern. Defaults to once, 0 repeats forever

        # check user input
        if images < 1:
            sys.exit("Bad number of images provided to configurePatternLut()")
            return
        if repeat < 0:
            sys.exit("Bad repeat number provided to configurePatternLut()")
            return

        self.log.debug("Configuring Pattern LUT...")

        # calculate and send the payload
        images = numToBits(images, 11)
        repeat = numToBits(repeat, 32)
        payload = bitsToBytes(repeat + '00000' + images)

        self.send('w', 0x1a31, payload)
        self.checkAllStatus()

    # See 2.4.4.3.4 "Pattern Display LUT Definition" in programmer's guide
    def definePattern(self, exposure):
        self.stopSequence()             # must stop sequence before sending a pattern

        self.log.debug("Defining pattern...")

        # See comments below in this function for more explanation
        index = 0               # we are only sending one image at a time, so index is always 0
        bitDepth = 8            # we are always using 8 bit images
        color = '100'           # system LED is on the blue channel
        triggerIn = 1
        darkTime = 0
        triggerOut = 0
        patternId = 0
        bitPosition = 0

        exposure = int(exposure * 1000) # convert exposure from ms to us

        # check user input
        #   min exposures vary by bit depth (exposures in us)
        #   read with command 0x1a42 - See 2.3.5.4 "Get Minimum LED Pattern Exposure" in Programmer's Guide
        #   bit depth:        1       2       3       4       5       6       7       8
        #   min exposure:     105     304     394     823     1215    1487    1998    4046
        minExposure = [105, 304, 394, 823, 1215, 1487, 1998, 4046]
        if exposure < minExposure[bitDepth- 1]:
            sys.exit("Too small of exposure passed to definePattern()")
            return
        if exposure > 0xFFFFFF:
            sys.exit("Too large of exposure passed to definePattern()")
            return

        payload = list(range(12))       # an array of bytes to be sent to form this internal LUT entry in the DLPC900

        # pattern index (valid range 0 - 511)
        payload[0] = index & 0xff               # byte 0
        payload[1] = (index >> 8) & 0xff        # byte 1

        # exposure time
        #    bits 31:24 - reserved
        #    bits 23:0 - exposure time in microseconds
        payload[2] = exposure & 0xff            # byte 2
        payload[3] = (exposure >> 8) & 0xff     # byte 3
        payload[4] = (exposure >> 16) & 0xff    # byte 4

        # image settings (byte 5)
        # bit 0 - clear the pattern after exposure. This is only applicable for 1 bit patterns
        #    with an external trigger. For other patterns, the clear is automatically handled.
        temp = int('1') & 0x1
        # bits 1:3 - bit depth
        #    b000 = 1 bit
        #    b001 = 2 bit
        #    b010 = 3 bit
        #    ...
        #    b111 = 8 bit
        temp |= ((bitDepth - 1) << 1) & 0x0e
        # bits 4:6 - color - in the Wintech, the LED is on the blue channel, in the Visitech it is on red
        #    b000 = All LEDs disabled
        #    b001 = Red
        #    b010 = Green
        #    b011 = Yellow (Green + Red)
        #    b100 = Blue
        #    b101 = Magenta (Blue + Red)
        #    b110 = Cyan (Blue + Green)
        #    b111 = White (Blue + Green + Red)
        temp |= (int(color) << 4) & 0x70
        # bit 7 - trigger/VSYNC
        #    1 = Wait for trigger before displaying the pattern
        #    0 = Continue running after previous pattern
        temp |= (triggerIn << 7) & 0x80

        payload[5] = int(temp)                  # byte 5

        # dark wait time
        #     bits 31:24 - reserved,
        #     bits 23:0 - dark display time following the exposure (in micro seconds))
        # temp = darkTime
        payload[6] = darkTime & 0xff            # byte 6
        payload[7] = (darkTime >> 8) & 0xff     # byte 7
        payload[8] = (darkTime >> 16) & 0xff    # byte 8

        # trigger 2
        #   bit 0 - trigger 2 setting
        #       1 = Disable trigger 2 output for this pattern
        #       0 = Enable trigger 2 output for this pattern
        #   bits 1:7 - reserved
        payload[9] = triggerOut                 # byte 9

        # image pattern settings
        #    bits 10:0 - Image pattern index (Not applicable in video pattern mode) Valid Range 0-255
        #    bits 115:11 - Bit position in the image pattern (Frame in video pattern mode) Valid range 0-23
        payload[10] = patternId                 # byte 10
        payload[11] = (bitPosition & 0x1f) << 3 # byte 11

        self.send('w', 0x1a34, payload)         # send payload
        self.checkAllStatus()
