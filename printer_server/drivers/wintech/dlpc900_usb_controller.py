"""DLPC9000 USB driver"""

import sys
import time
import atexit
import logging
import usb.core
import usb.util

INPUT_BIT_DEPTHS = {0: "30-bit", 1: "24-bit", 2: "20-bit", 3: "16-bit"}
INPUT_SOURCES = {
    0: "Primary parallel interface",
    1: "Internal test pattern generator",
    2: "Flash memory",
    3: "Solid curtain",
}
DISPLAY_MODES = {
    0: "Video mode",
    1: "Pre-stored pattern mode",
    2: "Video pattern mode",
    3: "Pattern On-The-Fly mode",
}
IT6535_POWER_MODES = {
    0: "Power-Down",
    1: "HDMI",
    2: "DisplayPort",
}
ERROR_CODES = {
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
}
HW_CONFIGURATION = {
    0: "Unknown hardware",
    1: "DLP6500",
    2: "DLP9000",
    3: "DLP670S",
    4: "DLP500YX",
}


def _read_payload_size(data):
    """Return the payload size of a response message from the
    DLPC900 by reading bytes 3 and 4 of the header."""
    return (data[3] << 8) + data[2]


def _reverse_pack_bytes(val, num_bytes):
    """Return a list of bytes packed in reverse order."""
    return [(val >> (i * 8)) & 0xFF for i in range(num_bytes)]


def _bytes_to_string(buffer, num_bytes=64):
    """Return a string representation of byte data using the first
    num_bytes of data.
    """
    return " ".join([hex(buffer[i]) for i in range(0, num_bytes)])


def _get_bits(x, l, r):
    """Return bits l:r in x, where l is the leftmost bit and r is the
    rightmost.

    For example, _get_bits(0b111001, 3, 0) would give '0b1001', and
    _get_bits(0b111001, 5, 2) would give '0b1110'.
    """
    if r > l:
        raise ValueError("'l' must be greater than or equal to 'r'")
    mask = (1 << (l - r + 1)) - 1
    return x >> r & mask


def _DLPC900_string(data):
    """Return the Python string representation of raw NULL terminated
    string data.
    """
    return data.tobytes().split(b"\x00")[0].decode("ascii")


def _dict_to_string(d):
    """Return a log friendly string from a dict."""
    return ", ".join(f"{key}: {value}" for key, value in d.items())


def is_set(x, n):
    """Return True if bit n in x is set, else return False."""
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
    # if is_set(hw_status, 3):
    #     msg += "Forced Swap Error occurred. "
    if is_set(hw_status, 4):
        msg += "Slave controller present and ready. "
    # if is_set(hw_status, 6):
    #     msg += "Sequencer has detected an error condition that caused an abort. "
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
    """Return a human readable error code. Returns 'Not defined.' if the
    code is undefined.
    """
    code = int(code)
    if code:
        code = ERROR_CODES.get(code, "Not defined.")
    return code


class DLPC900_USB_Controller:
    """USB interface for optical engine utilizing the TI DLPC900
    controller.
    """

    def __init__(self, log_level=logging.DEBUG):
        """Initialize a DLPC900_USB_Controller object.

        dev - handle to kernel driver
        transaction_counter - a counter used for the sequence byte
        is_idle - track the idle state of the DMD
        """
        self.log_level = log_level
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.dev = None
        self.transaction_counter = 0
        self.usb_io_counter = 0
        self.is_idle = False
        self.video_lock = False

    def _free_USB_driver(self):
        """Free the USB driver if it is already in use and set its
        configuration.
        """
        self.log.debug("Freeing device driver")
        for cfg in self.dev:
            for intf in cfg:
                n = intf.bInterfaceNumber
                if self.dev.is_kernel_driver_active(n):
                    try:
                        self.dev.detach_kernel_driver(n)
                        self.log.debug("Detached kernel driver from interface %s", n)
                    except usb.core.USBError as ex:
                        msg = f"Couldn't detach kernel driver from interface {n}: {ex}"
                        self.log.error(msg)

    def _HID_io_wrapper(self, fn, *args, **kwargs):
        """Wrap HID read and write methods so they have a greater
        likelihood of recovering from USBTimeoutError. If timeouts
        happen often, increase the timeout value passed to the read and
        write calls.
        """
        try:
            self.usb_io_counter += 1
            data = fn(*args, **kwargs)
        except usb.core.USBTimeoutError:
            self.log.warning("USB timeout occurred on %s", fn)
            self.log.warning("Number of HID writes: %s", self.usb_io_counter)
            self.log.warning("Number of transactions: %s", self.transaction_counter)
            time.sleep(1)
            self.dev.reset()
            time.sleep(1)
            self._free_USB_driver()
            self.dev.set_configuration()
            self.usb_io_counter += 1
            data = fn(*args, **kwargs)
        return data

    def _HID_read(self):
        """Wrapper function for USB HID read. The default IN endpoint
        for the DLPC900 is 0x81 so it is hard-coded here.
        """
        return self._HID_io_wrapper(self.dev.read, 0x81, 64, timeout=10000)

    def _HID_write(self, data=None):
        """Wrapper function for USB HID write. The default OUT endpoint
        for the DLPC900 is 0x1 so it is hard-coded here.
        """
        data = bytes(data)
        p_size = _read_payload_size(data)
        self.log.debug("USB HID write %s", _bytes_to_string(data, min(p_size + 4, 64)))
        return self._HID_io_wrapper(self.dev.write, 0x1, data, timeout=10000)

    def _DLPC900_command(self, mode, command, data=None):
        """Communicate with the DLPC900 controller over USB through a
        sequence of HID writes followed by HID reads. See 1.2.1 "USB
        Transaction Sequence" in the DLPC900 programmer's guide for more
        information.

        mode: 'r' for read or 'w' for write
        command: Two byte USB command specified in the programmer's
            guide.
        data: The rest of the parameters the command needs. See the
            programmer's guide for details on each command.

        The DLPC900 can accept up to 64 bytes per transaction. Command
        sequences larger than 64 bytes are broken into multiple write
        transactions of 64 bytes each, with the final write transaction
        zero padded up to 64 bytes. The DLPC900 then responds by placing
        a response in it's internal buffer and a series of one or more
        read transactions is issued to retrieve it. Only the first read
        and write transactions include header information.

        The HID protocol gives 64 bytes per read. If a payload is larger
        than 60 bytes, multiple reads are concatenated to get the full
        response. The first read contains 4 bytes of header data and 60
        bytes of payload data, where subsequent reads give 64 bytes of
        payload data with no header.

        This method also checks the flag byte to see if the error bit is
        set and logs additional info if it is. The header of the
        response is stripped and only the payload bytes ar returned.

        Header format:
        1 flag byte
        1 sequence byte
        2 byte payload length (little-endian)

        Payload format:
        2 byte USB command (litle-endian, only included in first write transaction)
        n bytes of data
        zero padding up to next 64 byte boundary
        """
        if data is None:
            data = []
        payload_length = len(data) + 2
        buffer = []
        buffer.append(0xC0 if mode == "r" else 0x40)
        buffer.append(self.transaction_counter & 0xFF)
        buffer.append(payload_length & 0xFF)
        buffer.append(payload_length >> 8)
        buffer.append(command & 0xFF)
        buffer.append(command >> 8)
        buffer.extend(data)
        buffer.extend([0x00] * (64 - len(buffer) % 64))
        for i in range(0, len(buffer), 64):
            self._HID_write(buffer[i : i + 64])
        self.transaction_counter += 1

        data = self._HID_read()
        payload_length = _read_payload_size(data)
        bytes_left = payload_length - 60
        while bytes_left > 0:
            data += self._HID_read()
            bytes_left -= 64
        self.log.debug("USB HID read  %s", _bytes_to_string(data, payload_length + 4))
        if is_set(data[0], 5):
            self.log.warning("Command not recognized or command failed")
            self.get_error_description()
        return data[4 : 4 + payload_length]

    def connect(self, vendor_id, product_id):
        """Find the DLPC900.

        The VID and PID combination representing the DLPC900
        controller is found.
        """
        self.log.info("Connecting to DLPC900 via USB...")
        self.dev = usb.core.find(idVendor=vendor_id, idProduct=product_id)
        if self.dev is None:
            msg = "DLPC900 light engine not found!"
            self.log.error(msg)
            return False
        try:
            self._free_USB_driver()
            self.dev.set_configuration()
            self.get_firmware_version()
            self.get_hardware_configuration_and_firmware_tag()
            atexit.register(self.disconnect)
        except:
            msg = "DLPC900 light engine not found!"
            self.log.error(msg)
            return False
        self.log.info("Connected to DLPC900 light engine")
        return True

    def initialize(self):
        self.log.debug("Initializing DLPC900 light engine")
        """Connect to the DLPC900 and perform associated setup.

        The driver is freed and the USB
        configuration is set. Then, a series of commands are issued
        to ready the system for normal 3D printing operation.
        """
        self.led_off()
        self.set_IT6535_power_mode("HDMI")
        self.set_display_mode("Video pattern mode")
        self.led_from_sequencer()
        self.set_long_axis_flip(False)
        self.set_short_axis_flip(True)
        self.log.info("DLPC900 light engine initialized")

    def disconnect(self):
        self.log.debug("Disconnecting from DLPC900 light engine")
        self.video_lock = False
        if self.dev is not None:
            try:
                self.stop_sequence()
                self.led_off()
                self. dev = None
                self.log.info("Disconnected from DLPC900 light engine")
            except:
                self.dev = None
                self.log.info("Unable to disconnect from DLPC900 light engine")

    def get_long_axis_flip(self):
        "Returns whether the long axis is flipped"
        self.log.debug("Get long axis flip")
        result = self._DLPC900_command("r", 0x1008)[0]
        cur_flip = _get_bits(result, 0, 0)
        self.log.debug("Long axis flip is set to %s", bool(cur_flip))

    def set_long_axis_flip(self, flip):
        """Set the long axis mirroring in the DLPC900"""
        self.log.debug("Set long axis mirroring to %s", flip)

        cur_flip = self.get_long_axis_flip()
        if flip == cur_flip:
            return
        self._DLPC900_command("w", 0x1008, [int(flip)])
        self.get_long_axis_flip()

    def get_short_axis_flip(self):
        "Returns whether the short axis is flipped"
        self.log.debug("Get short axis flip")
        result = self._DLPC900_command("r", 0x1009)[0]
        cur_flip = _get_bits(result, 0, 0)
        self.log.debug("Short axis flip is set to %s", bool(cur_flip))

    def set_short_axis_flip(self, flip):
        """Set the long axis mirroring in the DLPC900"""
        self.log.debug("Set short axis mirroring to %s", flip)

        cur_flip = self.get_short_axis_flip()
        if flip == cur_flip:
            return
        self._DLPC900_command("w", 0x1009, [int(flip)])
        self.get_short_axis_flip()

    def get_input_source_configuration(self):
        """Return the current input source configuration."""
        self.log.debug("Get input source configuration")
        config = self._DLPC900_command("r", 0x1A00)[0]
        source = INPUT_SOURCES.get(_get_bits(config, 2, 0))
        bit_depth = INPUT_BIT_DEPTHS.get(_get_bits(config, 4, 3))
        config = f"{source} ({bit_depth})"
        self.log.debug("Input source configuration is set to %s", config)
        return config

    def set_input_source_configuration(self, source):
        """Select the input source to be displayed by the DLPC900.

        See 2.3.3.2 'Input Source Configuration' in the programmer's
        guide.

        Only the 24-bit parallel option is implemented. Other options
        supported by the board are are 16, 20, 24, or 30-bit parallel
        port, Internal Test Pattern, and flash memory. All Pattern modes
        only use up to 24 bits. If a 30 bit video stream is input, the
        last two bits of data for each color are not used.
        """
        self.log.debug("Set input source configuration to %s", source)
        curr_source = self.get_input_source_configuration()
        if source == curr_source:
            return
        if source == "Primary parallel interface (24-bit)":
            self._DLPC900_command("w", 0x1A00, [0x8])
            time.sleep(2)
            self.get_input_source_configuration()
            self.check_all_status()
        else:
            self.log.warning("Unknown input source configuration %s", source)

    def get_display_mode(self):
        """Return the current display mode.

        See 2.4.1 'Display Mode Selection' in the programmer's guide for
        more details. See DISPLAY_MODES for valid modes.
        """
        self.log.debug("Get display mode")
        mode = self._DLPC900_command("r", 0x1A1B)[0]
        mode = DISPLAY_MODES.get(_get_bits(mode, 1, 0))
        self.log.debug("Display mode is set to %s", mode)
        return mode

    def set_display_mode(self, mode, log_level=logging.INFO):
        """Set the display mode.

        See 2.4.1 Display Mode Selection' in the programmer's guide. See
        DISPLAY_MODES for valid modes.

        To change to Video pattern mode, the system must first change to
        Video mode with the desired source enabled and sync must be
        locked before switching to Video Pattern mode. Once sync lock is
        achieved it takes about 300 ms to complete the transition to
        Video Pattern mode. If the display mode is read back before this
        time, it may not return the correct mode.
        """
        self.log.log(log_level, "Set display mode to %s", mode)
        curr_mode = self.get_display_mode()
        if mode == curr_mode:
            return
        try:
            data = next(key for key, value in DISPLAY_MODES.items() if value == mode)
        except StopIteration:
            self.log.warning("Unknown display mode %s", mode)
            return
        if mode == "Video pattern mode":
            self.set_IT6535_power_mode("HDMI", log_level=logging.DEBUG)
            self.set_display_mode("Video mode", log_level=logging.DEBUG)
            self.wait_for_video_lock()
            self.video_lock = True
        self._DLPC900_command("w", 0x1A1B, [data])
        time.sleep(1)
        self.get_display_mode()
        self.check_all_status()

    def wait_for_video_lock(self, timeout=10):
        """Block execution until video lock is acquired, with a timeout
        in seconds.
        """
        self.log.debug("Wait for video lock")
        start_time = time.time()
        while not is_set(self.get_main_status(), 3):
            time.sleep(0.5)
            if time.time() - start_time >= timeout:
                self.log.warning("Wait for video lock timed out.")
                self.get_main_status()
                return

    def get_IT6535_power_mode(self):
        """Return the current IT6535 power mode setting.

        See 2.3.5 'IT6535 Power Mode' in the programmer's guide. See
        IT6535_POWER_MODES for valid modes.
        """
        self.log.debug("Get IT6535 power mode")
        mode = self._DLPC900_command("r", 0x1A01)[0]
        mode = IT6535_POWER_MODES.get(_get_bits(mode, 1, 0))
        self.log.debug("IT6535 power mode is set to %s", mode)
        return mode

    def set_IT6535_power_mode(self, mode, log_level=logging.INFO):
        """Select an input source.

        See 2.3.5 'IT6535 Power Mode' in the programmer's guide for more
        details. See IT6535_POWER_MODES for valid modes. It takes about
        6 seconds to power up the IT6535 receiver.
        """
        self.log.log(log_level, "Set IT6535 power mode to %s", mode)
        curr_mode = self.get_IT6535_power_mode()
        if mode == curr_mode:
            return
        try:
            data = next(key for key, value in IT6535_POWER_MODES.items() if value == mode)
        except StopIteration:
            self.log.warning("Unknown IT6535 power mode %s", mode)
            return
        self._DLPC900_command("w", 0x1A01, [data])
        self.get_IT6535_power_mode()
        self.check_all_status()

    def get_hardware_status(self):
        """Return the hardware status.

        See 2.1.1 "Hardware Status" in the programmer's guide.
        """
        self.log.debug("Checking hardware status")
        response = self._DLPC900_command("r", 0x1A0A)[0]
        self.log.debug("Hardware status: %s", hex(response))
        status = parse_hardware_status(response)
        if status:
            self.log.warning(status)
        return response

    def get_system_status(self):
        """Return the system status.

        See 2.1.2 "System Status" in the programmer's guide.
        """
        self.log.debug("Checking system status")
        response = self._DLPC900_command("r", 0x1A0B)[0]
        status = parse_system_status(response)
        self.log.debug("System status: %s", hex(response))
        if status:
            self.log.warning(status)
        return response

    def get_main_status(self):
        """Return the main status.

        See 2.1.3 "Main Status" in the programmer's guide.
        """
        self.log.debug("Checking main status")
        response = self._DLPC900_command("r", 0x1A0C)[0]
        self.log.debug("Main status: %s", hex(response))
        status = parse_main_status(response)
        if status and self.video_lock:
            self.log.warning(status)
        return response

    def get_error_status(self):
        """Read error status.

        See 2.1.6 "Read Error Code" in the programmer's guide.
        """
        self.log.debug("Checking error codes")
        response = self._DLPC900_command("r", 0x0100)[0]
        self.log.debug("Error code: %s", hex(response))
        errors = parse_error_code(response)
        if errors:
            self.log.warning(errors)
        return response

    def check_all_status(self):
        """Read all status."""
        self.get_error_description()
        self.get_hardware_status()
        self.get_system_status()
        self.get_main_status()
        self.get_error_status()

    def get_led_power(self):
        """Return the current set LED power.

        Bytes 0 and 1 correspond to the RED and GREEN channels which are
        unsed in our system so only byte 2 is returned.
        """
        self.log.debug("Get LED power")
        power = self._DLPC900_command("r", 0x0B01)[2]
        self.log.debug("LED power is set to %s", power)
        return power

    def set_led_power(self, power):
        """Set the pulse duration of the LED PWM modulation output pin.

        The set value corresponds to a percentage of the LED current and
        can be set from 0 to 100% in 256 steps, where 0 is 0% and 255 is
        100%. See 2.3.5.2 "LED Driver Current" in the programmer's guide.

        CAUTION: Care should be taken when using this command. Improper
        use of this command can lead to damage to the system. The
        setting of the LED current depends on many system and
        application parameters (including projector thermal design, LED
        specifications, selected display mode, and so forth). Therefore,
        recommended and absolute-maximum settings vary greatly.

        Our system shipped with a default value of 0x64 which is 100/256
        or 39% max power. To be safe, I am leaving this as the maximum.
        """
        self.log.debug("Setting LED power to %s", power)
        if power < 0 or power > 100:
            self.log.warning("Bad LED power of %s. Should be between 0 and 100.", power)
        curr_power = self.get_led_power()
        if power == curr_power:
            return
        self._DLPC900_command("w", 0x0B01, [0, 0, power])
        self.check_all_status()

    def led_on(self):
        """Turn on the LED.

        See 2.3.5.1 "LED Enable Outputs" in the programmer's guide.
        """
        self.log.debug("LED turned on")
        self._DLPC900_command("w", 0x1A07, [0x4])
        self.check_all_status()

    def led_off(self):
        """Turn off the LED.

        See 2.3.5.1 "LED Enable Outputs" in the programmer's guide.
        """
        self.log.debug("LED turned off")
        self._DLPC900_command("w", 0x1A07, [0x0])
        self.check_all_status()

    def led_from_sequencer(self):
        """Set the LED to be controlled by the sequencer.

        See 2.3.5.1 "LED Enable Outputs" in the programmer's guide.
        """
        self.log.debug("LED set to run from sequencer")
        self._DLPC900_command("w", 0x1A07, [0xC])
        self.check_all_status()

    def idle_on(self):
        """Enable idle mode.

        See section 2.4.1.4 "DMD Idle Mode" in the programmer's guide.

        "It is strongly recommended that anytime the DMD is idle and not
        actively projecting data that the DMD Idle Mode be enabled to
        assist in maximizing DMD lifetime. For example, whenever the
        system is idle, between exposures if the application allows for
        it, or when the exposure pattern sequence is stopped. To enable
        this mode, the pattern sequences must first be stopped.
        To restart the pattern sequence, this mode must be disabled."
        """
        if not self.is_idle:
            self.log.debug("Idle mode enabled")
            self.is_idle = True
            self._DLPC900_command("w", 0x0201, [0x1])
            self.check_all_status()

    def idle_off(self):
        """Disable idle mode.

        See section 2.4.1.4 "DMD Idle Mode" in the programmer's guide."""
        if self.is_idle:
            self.log.debug("Idle mode disabled")
            self.is_idle = False
            self._DLPC900_command("w", 0x0201, [0x0])
            self.check_all_status()

    def standby(self):
        """Put DLPC900 into standby power mode.

        See 2.3.1.1 "Power Mode" in the programmer's guide.

        "The Power Control places the DLPC900 in a standby state and
        powers down the DMD interface. Enter Standby mode prior to any
        planned system power shutdowns to help prolong DMD lifetime.
        Standby mode should only be enabled after all data for the last
        frame to be displayed has been transferred to the DLPC900.
        Standby mode must be disabled prior to sending any new data."
        Status commands still work in idle mode.
        """
        self.log.debug("Standby mode enabled")
        self._DLPC900_command("w", 0x0200, [0x1])
        self.check_all_status()

    def wakeup(self):
        """Put DLPC900 into normal power mode.

        See 2.3.1.1 "Power Mode" in the programmer's guide.
        """
        self.log.debug("Standby mode disabled")
        self._DLPC900_command("w", 0x0200, [0x0])
        self.check_all_status()

    def software_reset(self):
        """Reset the internal DLPC900 software.

        A full reset takes about 7 seconds.
        """
        self.log.debug("Software reset")
        self._DLPC900_command("w", 0x0200, [0x2])
        time.sleep(7)
        self.check_all_status()

    def start_sequence(self):
        """Start the pattern display sequence.

        See 2.4.4.3.1 "Pattern Display Start/Stop" in the programmer's
        guide.
        """
        self.log.debug("Starting sequence")
        self._DLPC900_command("w", 0x1A24, [0x2])
        self.check_all_status()

    def pause_sequence(self):
        """Pause the pattern display sequence.

        See 2.4.4.3.1 "Pattern Display Start/Stop" in the programmer's
        guide.

        If a pattern is paused during exposure, the next start command
        will start the pattern sequence by re-displaying the current
        pattern in the sequence from the beginning.
        """
        self.log.debug("Pausing sequence")
        self._DLPC900_command("w", 0x1A24, [0x1])
        self.check_all_status()

    def stop_sequence(self):
        """Stop the pattern display sequence.

        See 2.4.4.3.1 "Pattern Display Start/Stop" in the programmer's
        guide.

        If a pattern is stopped during exposure, the next start command
        will start the pattern sequence by re-displaying the current
        pattern in the sequence from the beginning.
        """
        if self.sequencer_is_running():
            self.log.debug("Stopping sequence")
            self._DLPC900_command("w", 0x1A24, [0x0])
            self.check_all_status()

    def sequencer_is_running(self):
        """Return True if the sequencer is running, else return False."""
        self.log.debug("Check sequencer running")
        main_status = self.get_main_status()
        if is_set(main_status, 1):
            return True
        return False

    def configure_pattern_LUT(self, images=1, repeat=1):
        """Configure the pattern LUT. This must be called before
        defining any patterns.

        See 2.4.4.3.3 "Pattern Display LUT Configuration" in the
        programmer's guide.

        images - The number of patterns to be uploaded.
        repeat - The number of times to repeat each pattern. Defaults to
            1, 0 means repeat forever.
        """
        self.log.debug("Configuring Pattern LUT: %s patterns %s repeat", images, repeat)
        if images < 1:
            self.log.warning("Bad number of patterns: %s. Must be > 0", images)
            return
        if repeat < 0:
            self.log.warning("Bad repeat value: %s. Must be >= 0", images)
            return
        payload = _reverse_pack_bytes(images & 0x07FF, 2)
        payload.extend(_reverse_pack_bytes(repeat, 4))
        self._DLPC900_command("w", 0x1A31, payload)
        self.check_all_status()

    def define_pattern(self, exposure_time_ms):
        """Define a pattern.

        See 2.4.4.3.4 "Pattern Display LUT Definition" in the
        programmer's guide. The sequencer must be stopped before
        defining a new pattern.

        exposure - Exposure time in ms.

        The minimum exposure time varies with bit depth. Allowable
        exposure times can be read with the command 0x1a42. See 2.3.5.4
        "Get Minimum LED Pattern Exposure" in the programmer's guide.
        The minimums for this system are as follows (in us):
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
        self.log.debug("Defining pattern")
        index = 0
        bit_depth = 8
        color = 0b100
        trigger_in = 1
        clear_pattern = 1
        dark_time = 0
        trigger_out = 0
        pattern_id = 0
        bit_position = 0
        exposure_time_us = int(exposure_time_ms * 1000)
        min_exp_time_us = [105, 304, 394, 823, 1215, 1487, 1998, 4046]
        if exposure_time_us < min_exp_time_us[bit_depth - 1]:
            msg = "Too small of exposure passed to define_pattern()"
            self.log.error(msg)
        if exposure_time_us > 0xFFFFFF:
            msg = "Too large of exposure passed to define_pattern()"
            self.log.error(msg)

        payload = list(range(12))
        payload[0] = index & 0xFF
        payload[1] = (index >> 8) & 0xFF
        payload[2] = exposure_time_us & 0xFF
        payload[3] = (exposure_time_us >> 8) & 0xFF
        payload[4] = (exposure_time_us >> 16) & 0xFF
        temp = clear_pattern & 0x1
        temp |= ((bit_depth - 1) << 1) & 0x0E
        temp |= (int(color) << 4) & 0x70
        temp |= (trigger_in << 7) & 0x80
        payload[5] = temp
        payload[6] = dark_time & 0xFF
        payload[7] = (dark_time >> 8) & 0xFF
        payload[8] = (dark_time >> 16) & 0xFF
        payload[9] = trigger_out
        payload[10] = pattern_id
        payload[11] = (bit_position & 0x1F) << 3
        self._DLPC900_command("w", 0x1A34, payload)
        self.check_all_status()

    def get_firmware_version(self):
        """Return the version information of the DLPC900 firmware."""
        self.log.debug("Reading firmware version information")
        v = self._DLPC900_command("r", 0x0205)
        version_info = {
            "Application software": f"{v[3]}.{v[2]}{_DLPC900_string(v[0:1])}",
            "API software": f"{v[7]}.{v[6]}{_DLPC900_string(v[4:5])}",
            "Software configuration": f"{v[11]}.{v[10]}{_DLPC900_string(v[8:9])}",
            "Sequencer configuration": f"{v[15]}.{v[14]}{_DLPC900_string(v[12:13])}",
        }
        self.log.debug(_dict_to_string(version_info))
        return version_info

    def get_hardware_configuration_and_firmware_tag(self):
        """Return the hardware configuration of the system and the 31
        byte ASCII firmware tag.

        See 2.1.5 "Reading Hardware Configuration and Firmware Tag
        Information" in the programmer's guide.
        """
        self.log.debug("Reading hardware configuration and firmware tag")
        response = self._DLPC900_command("r", 0x0206)
        hw_config = HW_CONFIGURATION.get(response[0], "Hardware not defined")
        firmware_tag = _DLPC900_string(response[1:25])
        msg = {"Hardware config": f"{hw_config}", "Firmware tag": f"{firmware_tag}"}
        self.log.debug(_dict_to_string(msg))
        return msg

    def get_error_description(self):
        """Return the error descriptive string of the last executed
        command.

        An empty string means no error.
        """
        self.log.debug("Reading error description")
        response = self._DLPC900_command("r", 0x0101)
        response_string = _DLPC900_string(response)
        if response_string:
            self.log.warning("Error detected: %s", response_string)
        return response_string
