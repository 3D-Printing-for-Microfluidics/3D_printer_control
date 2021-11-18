"""Wintech USB driver"""

import sys
import time
import atexit
import logging
import usb.core
import usb.util


def num_to_bits(number, length):
    """Convert a number into a bit string of given length.
    number - number to convert
    length - length of resultant bit string
    """
    b = bin(number)[2:]
    padding = length - len(b)
    b = "0" * padding + b
    return b


def bits_to_bytes(bit_string):
    """Convert a bit string into a list of full bytes."""
    bytelist = []
    if len(bit_string) % 8 != 0:  # add 0 padding to fill last byte
        padding = 8 - len(bit_string) % 8
        bit_string = "0" * padding + bit_string
    for i in range(len(bit_string) // 8):  # pack bytes
        bytelist.append(int(bit_string[8 * i : 8 * (i + 1)], 2))
    bytelist.reverse()
    return bytelist


def decode_response(buffer):
    """Decode a byte list according to the payload length. See 1.2.1
    "USB Transaction Sequence" in the programmer's guide.

    If there are less than 4 bytes, the header to know how long the
    payload is is missing so return the string directly. Otherwise,
    calculate the length and use it to beuild the response.
    """
    if len(buffer) < 4:
        s = " ".join([hex(i) for i in buffer])
    else:
        s = ""
        # LSB of payload length comes first, +4 for header bytes
        length = buffer[2] + 0x100 * buffer[3] + 4
        for i in range(0, length):
            s = " ".join((s, hex(buffer[i])))
    return s


def is_set(x, n):
    """Returns True if bit n in x is set."""
    return x & 2 ** n != 0


def parse_hardware_status(hw_status):
    """Return human readable codes as parsed form the hardware status."""
    hw_status = int(hw_status)
    msg = ""
    if not is_set(hw_status, 0):
        msg += "Internal initialization failed. "
    if is_set(hw_status, 1):
        msg += "Incompatible controller or DMD. "
    if is_set(hw_status, 2):
        msg += "Multiple overlapping bias or reset operations are accessing the same "
        msg += "DMD block. "
    if is_set(hw_status, 3):
        msg += "Forced Swap Error occurred. "
    if is_set(hw_status, 4):
        msg += "Slave controller present and ready. "
    if is_set(hw_status, 6):
        msg += "Sequencer has detected an error condition that caused an abort. "
    if is_set(hw_status, 7):
        msg += "Sequencer detected an error. "
    return msg


def parse_system_status(sys_status):
    """Return human readable codes as parsed form the system status."""
    sys_status = int(sys_status)
    msg = ""
    if not is_set(sys_status, 0):
        msg += "= Internal Memory Test failed. "
    return msg


def parse_main_status(main_status):
    """Return human readable codes as parsed form the main status."""
    main_status = int(main_status)
    msg = ""
    if is_set(main_status, 0):
        msg += "DMD micromirrors are parked. "
    # else:
    #     msg += "DMD micromirrors are not parked. "
    # if not is_set(main_status, 1):
    #     msg += "Sequencer is stopped. "
    # else:
    #     msg += "Sequencer is running normally. "
    if is_set(main_status, 2):
        msg += "Video is frozen (Displaying single frame). "
    # else:
    #     msg += "Video is running (Normal frame change). "
    if not is_set(main_status, 3):
        msg += "External video source not locked. "
    # else:
    #     msg += "External video source locked. "
    if not is_set(main_status, 4):
        msg += "Port 1 video syncs not valid. "
    # else:
    #     msg += "Port 1 video syncs valid. "
    # if is_set(main_status, 5):
    #     msg += "Port 2 video syncs valid. "
    # else:
    #     msg += "Port 2 video syncs not valid. "
    return msg


def parse_error_code(code):
    """Return a human readable error code. Prints 'Not defined.' if the
    code is undefined.
    """
    code = int(code)
    if code:
        code = {
            0: "No error.",
            1: "Batch file checksum error.",
            2: "Device failure.",
            3: "Invalid command number.",
            4: "Incompatible controller / DMD.",
            5: "Command not allowed in current mode.",
            6: "Invalid command parameter.",
            7: "Item referred by the parameter is not present.",
            8: "Out of resource (RAM / Flash).",
            9: "Invalid BMP compression type.",
            10: "Pattern bit number out of range.",
            11: "Pattern BMP not present in flash.",
            12: "Pattern dark time is out of range.",
            13: "Signal delay parameter is out of range.",
            14: "Pattern exposure time is out of range.",
            15: "Pattern number is out of range.",
            16: "Invalid pattern definition (errors other than 9-15).",
            17: "Pattern image memory address is out of range.",
            255: "Internal Error.",
        }.get(code, "Not defined.")
    return code


class WintechUSB:
    """USB interface for Wintech optical engine utilizing the TI DLPC900
    controller.
    """

    def __init__(self, log_level=logging.DEBUG):

        """Initialize a WintechUSB object.

        dev - handle to kernel driver
        transaction_counter - a counter used for the sequence byte
        is_idle - track the idle state of the DMD
        """
        self.log_level = log_level
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.dev = None
        self.transaction_counter = 0
        self.is_idle = False

    def _free_USB_driver(self, device):
        """Free the USB driver if it is already in use."""
        self.log.info("Freeing device driver")
        for cfg in device:
            for intf in cfg:
                n = intf.bInterfaceNumber
                if device.is_kernel_driver_active(n):
                    try:
                        device.detach_kernel_driver(n)
                    except usb.core.USBError as e:
                        sys.exit(f"Couldn't detach kernel driver from interface {n}: {e}")

    def _HID_read(self, num_bytes=64):
        """Wrapper function for USB HID read. The default IN endpoint
        for the DLPC900 is 0x81 so it is hard-coded here.

        num_bytes: the number of bytes to read. The maximum at for one
        transaction on the DLPC900 is 64.
        """
        data = self.dev.read(0x81, num_bytes)
        # self.log.debug("READ endpoint %s: %s", hex(endpoint), decode_response(data))
        return data

    def _HID_write(self, data=None):
        """Wrapper function for USB HID write. The default OUT endpoint
        for the DLPC900 is 0x1 so it is hard-coded here.
        """
        # self.log.debug("USB HID WRITE %s", decode_response(data))
        self.dev.write(0x1, data, timeout=10000)

    def _HID_transaction_sequence(self, mode, command, data=None, sequence_byte=0x0):
        """Communicate with the DLPC900 controller over USB through a
        sequence of HID writes followed by an HID read. See 1.2.1 "USB
        Transaction Sequence" in the DLPC900 programmer's guide for more
        information.

        mode: 'r' for read or 'w' for write
        sequence_byte: The DLPC900 will respond with the same sequence
            byte that the host sent. The host can then match the
            sequence byte from the command it sent with the sequence
            byte from the DLPC900 response to know which command the
            response applies to.
        command: Two byte USB command specified in the programmer's
            guide.
        data: The rest of the parameters the command needs. See the
            programmer's guide for details on each command.
        """
        if data is None:
            data = []

        # format header
        buffer = []
        flag_byte = "11000000" if mode == "r" else "01000000"
        buffer.append(bits_to_bytes(flag_byte)[0])
        if sequence_byte == 0x0:
            sequence_byte = self.transaction_counter & 0xFF
        buffer.append(sequence_byte)

        # calculate the payload length (data +2 bytes for USB command)
        p_length = bits_to_bytes(num_to_bits(len(data) + 2, 16))
        buffer.append(p_length[0])  # add LSB then MSB
        buffer.append(p_length[1])

        # format USB command - LSB first, then MSB
        buffer.append(command & 0xFF)
        buffer.append(command >> 8)

        # format data and send in 64 byte packets
        if len(buffer) + len(data) < 65:
            for i in data:
                buffer.append(i)
            for i in range(64 - len(buffer)):
                buffer.append(0x00)  # pad unused space with zeroes
            self._HID_write(buffer)
        else:  # command will not fit into one transaction
            for i in range(64 - len(buffer)):
                buffer.append(data[i])
            self._HID_write(buffer)  # write first 64 bytes
            buffer = []  # clear the buffer
            j = 0
            while j < len(data) - 58:  # set up buffer in 64 byte increments
                buffer.append(data[j + 58])
                j = j + 1
                if j % 64 == 0:
                    self._HID_write(buffer)  # write next 64 bytes
                    buffer = []
            if j % 64 != 0:
                while j % 64 != 0:
                    buffer.append(0x00)  # zero pad last set of bytes up to 64
                    j = j + 1
                self._HID_write(buffer)  # write final 64 bytes
        self.transaction_counter += 1
        return self._HID_read()

    def connect(self, quick=False):
        """Finds and connect to the device and perform other setup.

        First looks for the VID and PID combination representing the
        DLPC900 controller. Next frees the USB driver and sets the
        configuration. If quick is False, also sets up the sequencer,
        video mode, and input source.
        """
        self.log.info("Connecting to DLPC900 via USB")
        self.dev = usb.core.find(idVendor=0x0451, idProduct=0xC900)
        if self.dev is None:
            sys.exit("DLPC900 not found. Is it connected and turned on?")
            return
        self._free_USB_driver(self.dev)
        self.dev.set_configuration()
        atexit.register(self.stop_sequence)
        atexit.register(self.led_off)

        if not quick:
            # self.stop_sequence()
            self.led_off()
            self.set_input_source_configuration("24-bit parallel")
            self.set_IT6535_power_mode(1)
            self.set_display_mode(2)
            self.led_from_sequencer()
            self.log.info("Setup complete.")

    def set_input_source_configuration(self, source="24-bit parallel"):
        """Select the input source to be displayed by the DLPC900.

        Only the 24-bit parallel option is implemented. Other options
        supported by the board are are 16, 20, 24, or 30-bit parallel
        port, Internal Test Pattern, and flash memory.
        """
        self.log.info("Set input source configuration to: %s", source)
        if source == "24-bit parallel":
            self._HID_transaction_sequence("w", 0x1A00, [0x8])
            time.sleep(2)
            self.check_all_status()

    def set_display_mode(self, mode):
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
        self.log.info("Set display mode to: %s", displayModes[mode])
        if mode < 0 or mode > 3:
            sys.exit("Bad display mode value passed in to set_display_mode()")
            return
        self._HID_transaction_sequence("w", 0x1A1B, [mode])
        time.sleep(5)
        self.check_all_status()

    def set_IT6535_power_mode(self, source):
        """Select an input source. See IT6535 Power Mode Command for
        more details. It takes about 6 seconds to power up the IT6535
        receiver.

        source:
            0 = Power-Down (Outputs will be tri-stated).
            1 = Power-Up for HDMI input.
            2 = Power-Up for DisplayPort input.
        """
        IT6535_power_modes = ["Power-down", "HDMI", "DisplayPort"]
        self.log.info("IT6535 power mode set to: %s", IT6535_power_modes[source])
        if source < 0 or source > 2:
            sys.exit("Bad source value passed in to set_IT6535_power_mode()")
        self._HID_transaction_sequence("w", 0x1A01, [source])
        time.sleep(6)
        self.check_all_status()

    def check_hardware_status(self):
        """Read hardware status. See 2.1.1 "Hardware Status" in the
        programmer's guide.
        """
        self.log.debug("Checking hardware status")
        response = self._HID_transaction_sequence("r", 0x1A0A)
        self.log.debug(hex(response[4]))
        status = parse_hardware_status(response[4])
        if status:
            self.log.warning(status)

    def check_system_status(self):
        """Read system status. See 2.1.2 "System Status" in the
        programmer's guide.
        """
        self.log.debug("Checking system status")
        response = self._HID_transaction_sequence("r", 0x1A0B)
        self.log.debug(hex(response[4]))
        status = parse_system_status(response[4])
        if status:
            self.log.warning(status)

    def check_main_status(self):
        """Read main status. See 2.1.3 "Main Status" in the programmer's
        guide.
        """
        self.log.debug("Checking main status")
        response = self._HID_transaction_sequence("r", 0x1A0C)
        self.log.debug(hex(response[4]))
        status = parse_main_status(response[4])
        if status:
            self.log.warning(status)

    def check_error_status(self):
        """Read error status. See 2.1.6 "Read Error Code" in the
        programmer's guide.
        """
        self.log.debug("Checking for errors")
        response = self._HID_transaction_sequence("r", 0x0100)
        self.log.debug(hex(response[4]))
        errors = parse_error_code(response[4])
        if errors:
            self.log.warning(errors)

    def check_all_status(self):
        """Read all status."""
        self.check_hardware_status()
        self.check_system_status()
        self.check_main_status()
        self.check_error_status()

    def set_led_power(self, power):
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
        self._HID_transaction_sequence("w", 0x0B01, [0, 0, power])
        self.check_all_status()

    def led_on(self):
        """Turn on the LED. See 2.3.5.1 "LED Enable Outputs" in the
        programmer's guide.
        """
        self.log.info("LED turned on")
        self._HID_transaction_sequence("w", 0x1A07, [0x4])
        self.check_all_status()

    def led_off(self):
        """Turn off the LED. See 2.3.5.1 "LED Enable Outputs" in the
        programmer's guide.
        """
        self.log.info("LED turned off")
        self._HID_transaction_sequence("w", 0x1A07, [0x0])
        self.check_all_status()

    def led_from_sequencer(self):
        """Set the LED to be controlled by the sequencer. See 2.3.5.1
        "LED Enable Outputs" in the programmer's guide.
        """
        self.log.info("LED set to run from sequencer")
        self._HID_transaction_sequence("w", 0x1A07, [0xC])
        self.check_all_status()

    def idle_on(self):
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
        if not self.is_idle:
            self.log.info("Idle mode enabled")
            self.is_idle = True
            self._HID_transaction_sequence("w", 0x0201, [0x1])
            self.check_all_status()

    def idle_off(self):
        """Enable idle mode. - See section 2.4.1.4 "DMD Idle Mode" in
        the programmer's guide."""
        if self.is_idle:
            self.log.info("Idle mode disabled")
            self.is_idle = False
            self._HID_transaction_sequence("w", 0x0201, [0x0])
            self.check_all_status()

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
        self._HID_transaction_sequence("w", 0x0200, [0x1])
        self.check_all_status()

    def wakeup(self):
        """Put DLPC900 into normal power mode. See 2.3.1.1 "Power Mode"
        in the programmer's guide.
        """
        self._HID_transaction_sequence("w", 0x0200, [0x0])
        self.check_all_status()

    def software_reset(self):
        """Reset the internal DLPC900 software. A full reset takes about
        7 seconds.
        """
        self._HID_transaction_sequence("w", 0x0200, [0x2])
        time.sleep(7)
        self.check_all_status()

    def start_sequence(self):
        """Start the pattern display sequence. See 2.4.4.3.1 "Pattern
        Display Start/Stop" in the programmer's guide.
        """
        self.log.info("Starting sequence")
        self._HID_transaction_sequence("w", 0x1A24, [0x2])
        self.check_all_status()

    def pause_sequence(self):
        """Pause the pattern display sequence. See 2.4.4.3.1 "Pattern
        Display Start/Stop" in the programmer's guide.

        If a pattern is paused during exposure, the next start command
        will start the pattern sequence by re-displaying the current
        pattern in the sequence from the beginning.
        """
        self.log.info("Pausing sequence")
        self._HID_transaction_sequence("w", 0x1A24, [0x1])
        self.check_all_status()

    def stop_sequence(self):
        """Stop the pattern display sequence. See 2.4.4.3.1 "Pattern
        Display Start/Stop" in the programmer's guide.

        If a pattern is stopped during exposure, the next start command
        will start the pattern sequence by re-displaying the current
        pattern in the sequence from the beginning.
        """
        self.log.info("Stopping sequence")
        self._HID_transaction_sequence("w", 0x1A24, [0x0])
        self.check_all_status()

    def configure_pattern_LUT(self, images=1, repeat=1):
        """Configure the pattern LUT. This must be called before
        defining any patterns. See 2.4.4.3.3 "Pattern Display LUT
        Configuration" in the programmer's guide.

        images - The number of patterns to be uploaded.
        repeat - The number of times to repeat each pattern. Defaults to
            1, 0 means repeat forever.
        """
        if images < 1:
            sys.exit("Bad number of images provided to configure_pattern_LUT()")
        if repeat < 0:
            sys.exit("Bad repeat number provided to configure_pattern_LUT()")
        self.log.info("Configuring Pattern LUT")
        payload = bits_to_bytes(
            num_to_bits(repeat, 32) + "00000" + num_to_bits(images, 11)
        )
        self._HID_transaction_sequence("w", 0x1A31, payload)
        self.check_all_status()

    def define_pattern(self, exposure):
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
            Bits 1-3: Image bit depth. b000 = 1, b001 = 2, b111 = 8.
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
        self.log.info("Defining pattern")
        # self.stop_sequence()
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
            sys.exit("Too small of exposure passed to define_pattern()")
        if exposure > 0xFFFFFF:
            sys.exit("Too large of exposure passed to define_pattern()")

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
        self._HID_transaction_sequence("w", 0x1A34, payload)
        self.check_all_status()
