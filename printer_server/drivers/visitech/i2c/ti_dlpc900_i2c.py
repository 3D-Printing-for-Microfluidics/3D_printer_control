import time
import json
import logging
from smbus2 import SMBus


TI_I2C_ADDR = 0x1A
TI_REG_R_PIXEL_MODE = 0x03
TI_REG_W_PIXEL_MODE = 0x83
TI_REG_R_TEST_PATTERN = 0x0A
TI_REG_W_TEST_PATTERN = 0x8A
TI_REG_R_IT6535 = 0x0C
TI_REG_W_IT6535 = 0x8C
TI_REG_R_HW_STATUS = 0x20
TI_REG_R_SYS_STATUS = 0x21
TI_REG_R_MAIN_STATUS = 0x22
TI_REG_R_ERROR_CODE = 0x32
TI_REG_R_SEQUENCE = 0x65
TI_REG_W_SEQUENCE = 0xE5
TI_REG_R_DISPLAY_MODE = 0x69
TI_REG_W_DISPLAY_MODE = 0xE9
TI_REG_R_PATTERN_DISPLAY_LUT_CONFIG = 0x75
TI_REG_W_PATTERN_DISPLAY_LUT_CONFIG = 0xF5  # Bit 0-10 = Numer of LUT entries, 15:11 reserved, 16:47 Number of times to repeat pattern sequence  0=forever
TI_REG_W_PATTERN_DISPLAY_LUT = 0xF8
TI_SEQUENCE_ON = 0x2
TI_SEQUENCE_OFF = 0x0
TI_SEQUENCE_PAUSE = 0x1
TI_IT6536_OFF = 0x0
TI_IT6536_HDMI = 0x1
TI_IT6536_DISPLAYPORT = 0x2
TI_DISPLAY_MODE_NORMAL = 0x0
TI_DISPLAY_MODE_PRE_STORED = 0x1
TI_DISPLAY_MODE_VIDEO_PATTERN = 0x2
TI_DISPLAY_MODE_ON_THE_FLY = 0x3

# helper function for converting error codes to human readable format
def convert_error_code(code):
    return {
        0: "No error",
        1: "Batch file checksum error",
        2: "Device failure",
        3: "Invalid command number",
        4: "Incompatible controller / DMD",
        5: "Command not allowed in current mode",
        6: "Invalid command parameter",
        7: "Item referred by the parameter is not present",
        8: "Out of resource (RAM / Flash)",
        9: "Invalid BMP compression type",
        10: "Pattern bit number out of range",
        11: "Pattern BMP not present in flash",
        12: "Pattern dark time is out of range",
        13: "Signal delay parameter is out of range",
        14: "Pattern exposure time is out of range",
        15: "Pattern number is out of range",
        16: "Invalid pattern definition (errors other than 9-15)",
        17: "Pattern image memory address is out of range",
        255: "Internal Error",
    }.get(
        code, "Not defined"
    )  # "Not defined" is default if code is not found


class DLPC900_Exception(Exception):
    def __init__(self, arg):
        self.arg = arg
        super().__init__(arg)


class TI_DLPC900_I2C:
    I2C_IO_DELAY = 0.01  # Delay after every I2C command, 10ms

    def __init__(self, verbosity=logging.DEBUG):
        """Initialize the i2c bus and set defaults."""
        self.i2c_bus_num = 1
        self.i2c_bus = SMBus(self.i2c_bus_num)
        self.address = TI_I2C_ADDR
        self.power = None
        self.verbosity = verbosity
        self.logger = None

    def read_register(self, register, retry=3):
        """Read from the specified DMD register up to retry times."""
        self.log(logging.DEBUG, "Reading DMD register {}".format(register))
        caught_exception = None
        for _ in range(retry):
            try:
                result = self.i2c_bus.read_byte_data(self.address, int(register))
                time.sleep(self.I2C_IO_DELAY)
                return result
            except Exception as ex:
                self.log(logging.INFO, "I2C read error {}".format(ex))
                caught_exception = ex
                time.sleep(1)  # wait 1 second to retry
        self.log(
            logging.ERROR,
            "I2C read error in Visitech! {} sequential reads failed".format(retry),
        )
        raise caught_exception

    def write_register(self, register, val, retry=3):
        """Write to the specified DMD register up to retry times."""
        self.log(logging.DEBUG, "Writing {} to DMD register {}".format(val, register))
        caught_exception = None
        for _ in range(retry):
            try:
                self.i2c_bus.write_byte_data(self.address, register, int(val))
                time.sleep(self.I2C_IO_DELAY)
                success = True
                return
            except Exception as ex:
                self.log(logging.INFO, "I2C write error {}".format(ex))
                caught_exception = ex
                time.sleep(1)  # wait 1 second to retry
        self.log(
            logging.ERROR,
            "I2C write error in Visitech! {} sequential writes failed".format(retry),
        )
        raise caught_exception

    def log(self, lvl, msg):
        """Log message.

        If no logger is supplied, print the std output.
        """
        try:
            self.logger.log(lvl, msg)
        except AttributeError:
            if lvl >= self.verbosity:
                print(f"{msg}")

    def load_default_configuration(self):
        """Load the default hardware configuration."""
        self.get_all_status()
        self.stop_sequencer()
        self.get_all_status()
        self.set_pixel_mode("Single")
        self.get_all_status()
        self.set_video_source("HDMI")
        self.get_all_status()
        self.set_dmd_operation_mode("Video pattern mode")
        self.get_all_status()

    def get_hardware_status(self):
        """Read the DMD Hardware Status register.

        Provides status information on the sequencer, DMD controller, and
        initialization of the DLPC900 board. See "Hardware Status" in DLPC900 docs.
        """
        status = self.read_register(TI_REG_R_HW_STATUS)
        return status

    def get_system_status(self):
        """Read the DMD System Status register.

        Provides the DLPC900 status on internal memory tests.
        See "System Status" in DLPC900 docs.
        """
        status = self.read_register(TI_REG_R_SYS_STATUS)
        return status

    def get_main_status(self):
        """Read the DMD Main Status register.

        Provides the status of DMD park and DLPC900 sequencer, frame buffer, and
        gamma correction. See "Main Status" in DLPC900 docs.
        """
        status = self.read_register(TI_REG_R_MAIN_STATUS)
        return status

    def get_error_code(self):
        """Read the last error code.

        Retrieves the error code number from the DLPC900 of the
        last executed command. See "Read Error Code" in DLPC900 docs.
        """
        error = self.read_register(TI_REG_R_ERROR_CODE)
        return convert_error_code(error)

    def get_all_status(self):
        """Return all status register output as a string"""
        return json.dumps(
            {
                "hardware status": self.get_hardware_status(),
                "system status": self.get_system_status(),
                "main status": self.get_main_status(),
                "error status": self.get_error_code(),
            },
            indent=2,
            sort_keys=True,
        )

    def start_sequencer(self):
        """Start the DMD sequencer."""
        self.log(logging.INFO, "Start sequencer")
        self.write_register(TI_REG_W_SEQUENCE, TI_SEQUENCE_ON)

    def stop_sequencer(self):
        """Stop the DMD sequencer."""
        self.log(logging.INFO, "Stop sequencer")
        self.write_register(TI_REG_W_SEQUENCE, TI_SEQUENCE_OFF)

    def pause_sequencer(self):
        """Pause the DMD sequencer."""
        self.log(logging.INFO, "Pause sequencer")
        self.write_register(TI_REG_W_SEQUENCE, TI_SEQUENCE_PAUSE)

    def set_dmd_operation_mode(self, mode):
        """Set the DMD display mode.

        See 2.4.1 "Display Mode Selection" in DLPC900 Programmers Guide.
        """
        pattern_modes = {
            "Video mode": TI_DISPLAY_MODE_NORMAL,
            "Pre-stored pattern mode": TI_DISPLAY_MODE_PRE_STORED,  # images from flash
            "Video pattern mode": TI_DISPLAY_MODE_VIDEO_PATTERN,
            "Pattern On-The-Fly mode": TI_DISPLAY_MODE_ON_THE_FLY,  # images loaded through USB/I2C
        }
        self.log(logging.INFO, "Set DMD operation mode to: {}".format(mode))
        time.sleep(5)  # must wait for at least 5 seconds to read or write display mode
        if mode in pattern_modes.keys():
            self.write_register(TI_REG_W_DISPLAY_MODE, pattern_modes[mode])
        else:
            self.log(logging.ERROR, "Bad video mode supplied: {}".format(mode))

    def set_video_source(self, source):
        """Select the video input for the DLPC900 board.

        The IT6535 Power Mode command allows the user to power-down and tri-state the IT6535 digital receiver
        data and sync outputs. This command is ignored if the IT6535 is not present or has been disabled in the
        App Defaults Settings found in the DLP LightCrafter 6500 & 9000 GUI Firmware tab.

        See 2.3.4.3 "IT6535 Power Mode" in the DLPC900 Programmers Guide.
        """

        video_sources = {
            "HDMI": TI_IT6536_HDMI,  # up to 30 Hz
            "DisplayPort": TI_IT6536_DISPLAYPORT,  # up to 60 Hz
        }
        self.log(logging.INFO, "Set video source to: {}".format(source))
        if source in video_sources.keys():
            self.write_register(TI_REG_W_IT6535, video_sources[source])
        else:
            self.log(logging.ERROR, "Bad video source supplied: {}".format(source))

    def set_pixel_mode(self, mode):
        """Set the pixel mode and clock configuration.

        Select which port the RGB data is on and which pixel clock, data enable, and syncs to
        use. The user must select the correct port and clock configuration according to the PCB layout routing.
        See 2.3.3.1 "Port and Clock Configuration" in DLPC900 Programmers Guide.

        1 byte
           bits 1:0 - pixel mode
               0 = Data Port 1, Single Pixel mode
               1 = Data Port 2, Single Pixel mode
               2 = Data Port 1-2, Dual Pixel mode. Even pixel on port 1, Odd pixel on port 2
               3 = Data Port 2-1, Dual Pixel mode. Even pixel on port 2, Odd pixel on port 1
           bits 3:2 - pixel clock
               0 = Pixel Clock 1
               1 = Pixel Clock 2
               2 = Pixel Clock 3
               3 = Reserved
           bit 4 - data enable
               0 = Data Enable 1
               1 = Data Enable 2
           bit 5 - vsync select
               0 = P1 VSync and P1 HSync
               1 = P2 VSync and P2 HSync
        """
        pixel_modes = {"Single": 0x0, "Dual": 0x2}
        self.log(logging.INFO, "Set pixel mode to: {}".format(mode))
        if mode in pixel_modes.keys():
            self.write_register(TI_REG_W_PIXEL_MODE, pixel_modes[mode])
        else:
            self.log(logging.ERROR, "Bad pixel mode supplied: {}".format(mode))

    def setInternalImage(self, num):
        """Display an image from the DLPC900 internal flash memory.

        Valid range is 0-10.
        """
        self.log(logging.INFO, "Set internal image to number {}".format(num))
        self.write_register(TI_REG_W_DISPLAY_MODE, TI_DISPLAY_MODE_PRE_STORED)
        self.write_register(TI_REG_W_TEST_PATTERN, num)

    def set_sequencer_lut_definition(self, exposure, bitdepth=7):
        """Define a sequencer pattern and write it to the DMD pattern
        LUT register.

        The Pattern Display LUT Definition contains the definition of each pattern to be displayed during the
        pattern sequence. Display Mode and Pattern Display LUT Configuration must be set before sending
        any pattern LUT definition data. If the Pattern Display Data Input Source is set to streaming, the
        image indexes do not need to be set. Regardless of the input source, the pattern definition must be set.

        See 2.4.4.3.4 "Pattern Display LUT Definition" in DLPC900 Programmers Guide

        bytes 0-1: pattern index (valid range 0 - 511)
        bytes 2-4: exposure time in microseconds
            bits 31:24 of byte 4 are reserved
            bits 23:0 - exposure time in microseconds
        byte 5: image settings
            bit 0 - clear the pattern after exposure. This is only applicable for 1 bit patterns
                    with an external trigger. For other patterns, the clear is automatically handled.
            bits 1:3 - bit depth
                    b000 = 1 bit
                    b001 = 2 bit
                    b010 = 3 bit
                    ...
                    b111 = 8 bit
            bits 4:6 - color - in the Wintech, the LED is on the blue channel, in the Visitech it is on red
                    b000 = All LEDs disabled
                    b001 = Red
                    b010 = Green
                    b011 = Yellow (Green + Red)
                    b100 = Blue
                    b101 = Magenta (Blue + Red)
                    b110 = Cyan (Blue + Green)
                    b111 = White (Blue + Green + Red)
            bit 7 - trigger/VSYNC
                    1 = Wait for trigger before displaying the pattern
                    0 = Continue running after previous pattern
        bytes 6-8: dark display time following the exposure (in micro seconds)
            bits 31-24 in byte 8 are reserved
        byte 9: External trigger enable - allows image to be triggered from external signal
            bit 0 - trigger 2 setting
                1 = Disable trigger 2 output for this pattern
                0 = Enable trigger 2 output for this pattern
            bits 1:7 - reserved
        bytes 10-11: image pattern settings
            bits 10:0 - Image pattern index (Not applicable in video pattern mode) Valid Range 0-255
            bits 115:11 - Bit position in the image pattern (Frame in video pattern mode) Valid range 0-23
        """
        self.log(
            logging.INFO,
            "Set sequencer LUT definition {} {}".format(exposure, bitdepth),
        )

        color = 1  # LED is on Red channel in the Visitech
        clear = 1
        darktime = 0
        bit_index = 0
        pattern_index = 0
        wait_for_trigger = 1
        exposure = int(exposure)

        buffer = bytearray(12)
        buffer[0] = pattern_index & 0xFF
        buffer[1] = pattern_index >> 8 & 0xFF
        buffer[2] = exposure & 0xFF
        buffer[3] = exposure >> 8 & 0xFF
        buffer[4] = exposure >> 16 & 0xFF
        # buffer[5] = byte5
        buffer[5] = (
            clear & 0x1
            | bitdepth << 1 & 0x0E
            | color << 4 & 0x70
            | wait_for_trigger << 7 & 0x80
        )
        buffer[6] = darktime & 0xFF
        buffer[7] = darktime >> 8 & 0xFF
        buffer[8] = darktime >> 16 & 0xFF
        buffer[9] = 0
        buffer[10] = 0
        buffer[11] = (bit_index & 0x1F) << 3

        self.i2c_bus.write_i2c_block_data(
            self.address, TI_REG_W_PATTERN_DISPLAY_LUT, buffer
        )
        time.sleep(self.I2C_IO_DELAY)

    def set_sequencer_lut_config(self, num_sequences=1, repeats=1):
        """Configure the DMD sequencer pattern display LUT.

        The Pattern Display LUT Configuration command controls the execution of patterns stored in the lookup
        table (LUT). Before executing this command, stop the current pattern sequence.

        See 2.4.4.3.3 "Pattern Display LUT Configuration" in DLPC900 Programmer's Guide.

        bytes 0-1
            bits 0-10 - Number of LUT entries (range 0 through 511)
            0 = Zero entries
            1 = One entries
            ...
            512 = 512 entries
        bytes 2-5 - Number of times to repeat the pattern sequence
            0 = repeat forever
        """
        self.log(
            logging.INFO,
            "Set sequencer LUT config to: {} sequences, {} repeats".format(
                num_sequences, repeats
            ),
        )
        self.stop_sequencer()  # sequencer must be stopped before writing config
        num_sequences = int(num_sequences).to_bytes(2, byteorder="little")
        repeats = int(repeats).to_bytes(4, byteorder="little")
        lut_config = bytearray(num_sequences + repeats)
        self.i2c_bus.write_i2c_block_data(
            self.address, TI_REG_W_PATTERN_DISPLAY_LUT_CONFIG, lut_config
        )
        time.sleep(self.I2C_IO_DELAY)


if __name__ == "__main__":
    dmd = TI_DLPC900_I2C(verbosity=logging.DEBUG)
    print(f"{dmd.get_all_status()}")
