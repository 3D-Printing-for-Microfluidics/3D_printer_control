# -*- coding: utf-8 -*-
"""
Light engine I2C module for Raspberry Pi
========================================
Here, we take advantage of the existing I2C bus on
Raspberry Pi, and uses it to control light engine directly.
"""
import sys
import time
import atexit
import logging
import pigpio
from smbus2 import SMBus
from .screen import ScreenThread

# helper function for converting error codes to human readable format
def convert_error_code(code):
    return {
        0: 'No error',
        1: 'Batch file checksum error',
        2: 'Device failure',
        3: 'Invalid command number',
        4: 'Incompatible controller / DMD',
        5: 'Command not allowed in current mode',
        6: 'Invalid command parameter',
        7: 'Item referred by the parameter is not present',
        8: 'Out of resource (RAM / Flash)',
        9: 'Invalid BMP compression type',
        10: 'Pattern bit number out of range',
        11: 'Pattern BMP not present in flash',
        12: 'Pattern dark time is out of range',
        13: 'Signal delay parameter is out of range',
        14: 'Pattern exposure time is out of range',
        15: 'Pattern number is out of range',
        16: 'Invalid pattern definition (errors other than 9-15)',
        17: 'Pattern image memory address is out of range',
        255: 'Internal Error'
    }.get(code, "Not defined")    # "Not defined" is default if code is not found

# ================ TI Constants ================

TI_REG_R_TESTIMAGE = 0x00
TI_REG_W_TESTIMAGE = 0x80
TI_REG_R_PIXEL_MODE = 0X03
TI_REG_W_PIXEL_MODE = 0X83
TI_REG_R_FLIP_LONG = 0x08
TI_REG_W_FLIP_LONG = 0x88
TI_REG_R_FLIP_SHORT = 0x09
TI_REG_W_FLIP_SHORT = 0x89
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
TI_REG_R_TRIGGER_OUT1 = 0x6A
TI_REG_W_TRIGGER_OUT1 = 0xEA
TI_REG_R_INVERT_DATA = 0x74
TI_REG_W_INVERT_DATA = 0xF4
TI_REG_R_PATTERN_DISPLAY_LUT_CONFIG = 0x75
TI_REG_W_PATTERN_DISPLAY_LUT_CONFIG = 0xF5 # Bit 0-10 = Numer of LUT entries, 15:11 reserved, 16:47 Number of times to repeat pattern sequence  0=forever
TI_REG_W_PATTERN_DISPLAY_LUT = 0xF8
TI_I2C_WADDR = 0x34
TI_I2C_RADDR = 0x35
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

# ================ Visitech Constants ================

LED_I2C_WADDR = 0x44
LED_I2C_RADDR = 0x45
LED_SV_UPDATE_REGISTER = 0x10
LED_AMPLITUDE_REGISTER = 0x14
LED_PFACTOR_REGISER = 0x24
LED_IFACTOR_REGISTER = 0x28
LED_LEDTEMP_REGISTER = 0x34
LED_OCPVALUE_REGISTER = 0x4C
LED_OPPVALUE_REGISTER = 0x54
LED_PWM_KEEP_OFF_REGISTER = 0x78
LED_LED_TEMP_LIMIT_REGISTER = 0x80
LED_TEST_REGISTER = 0x340
LED_STICKYBITS_REGISTER = 0x358     # Sticky bits: (4:OCP (3: Door_open (2: Fan stopped (1: Board_overtemp, (0: LED_overtemp
LED_BOARDTEMP_REGISTER = 0x370
LED_BOARD_TEMP_LIMIT_REGISTER = 0x378
NUM_SEQUENCE_COMMAND_VAR = 7
MAX_NUM_PATTERNS_IN_SEQ = 512
OCP_AMP_PER_UNIT_HW_VER1 = 0.196

# Defualt values to initialize LED
DEF_PWM_KEEP_OFF = 1
DEF_PFACTOR = 100
DEF_IFACTOR = 25
DEF_LED_TEMP_LIMIT = 400
DEF_BOARD_TEMP_LIMIT = 70
# DEF_LED_TEMP_LIMIT = 1000    # ?? LED temp limit: 50 deg C
# DEF_BOARD_TEMP_LIMIT = 90    # ?? Board temp limit: 70 deg C
DEF_OCP_AMP = 20                # Default OCP value - over current protection
DEF_OPP_HW_VER_1 = 275          # Default OPP values for different hardware versions

# # ====================== Errors ==========================

# ERROR_OK = 0
# ERROR_DLN_ADAPTER_OPEN = 1
# ERROR_GET_I2C_PORT_COUNT = 2
# ERROR_NO_I2C_PORTS = 3
# ERROR_DLN_SERVER_CONNECT_FAILED = 4
# ERROR_MASTER_SET_FREQUENCY_FAILED = 5
# WARNING_FREQUENCY_ROUNDED = 6
# ERROR_GET_FREQUENCY_FAILED = 7
# ERROR_MASTER_ENABLE_FAILED = 8
# ERROR_MASTER_DISABLE_FAILED = 9
# ERROR_MASTER_SCAN_FAILED = 10
# ERROR_MASTER_IS_ENABLED_FAILED = 11
# ERROR_SET_REPLY_COUNT_FAILED = 12
# ERROR_GET_REPLY_COUNT = 13
# ERROR_UNVALID_INPUT = 14
# ERROR_READ_FAILED = 15
# ERROR_WRITE_FAILED = 16
# ERROR_INVALID_WRITE_DATA = 17
ERROR_SEQUENCE_TO_MANY_PATTERNS = 18
# ERROR_COULD_NOT_FIND_SEQUENCE_FILE = 19
ERROR_COULD_NOT_FIND_ANY_LINES_IN_SEQUENCE_FILE = 20
# ERROR_MISSING_ARGUMENTS = 21
# ERROR_COMMAND_ARGUMENT_MISMATCH = 22
# ERROR_TO_HIGH_IMAGE_NUM = 23
# ERROR_TO_HIGH_LED_AMPLITUDE = 24
ERROR_SEQUENCE_NUM_ARGS = 1000
# ERROR_SEQUENCE_VALUES = 0x10000
# # LAST HEX DIGIT IS ARGUMENT NUM, hex digit 3,2,1 is line num
# LED_TEMP_RETURN_BASE = 2000
# LED_BOARD_TEMP_RETURN_BASE = 3000
# LED_STICKY_RETURN_BASE = 4000
# TI_SEQUENCE_RETURN_BASE = 5000

class Projector:
    """This class is built on the ``pigpio`` library.
    :param pi: a ``pigpio.pi`` object. If not specified when
               creating :py:class:`LightEngineI2C` object, the
               :py:meth:`init_pi` must be called before any
               further usage of I2C related
               operation.
    :param bus: physical I2C bus on Raspberry Pi.
                The Raspberry Pi has 2 physical I2C
                buses, 0 and 1. Here we use 1 by default.
    :param logger: a ``logging.logger`` object. If not specified,
                   the ``print`` function will be used.
    """
    I2C_IO_DELAY = 0.01   # Delay after every I2C command, 10ms

    def __init__(self, resolution, fullscreen=True):
        self.bus_num = 1
        self.bus = SMBus(self.bus_num)
        self.pi = pigpio.pi()
        self.led = None
        self.dmd = None
        self.dmd_addr = TI_I2C_RADDR>>1
        self.led_addr = LED_I2C_WADDR>>1
        self.resolution = resolution
        self.fullscreen = fullscreen
        self.max_exp_time = 10000       # max single projection time in ms
        self.ledPower = None

        # setup screen thread
        self.screenThread = ScreenThread(self.resolution, self.fullscreen)

        # register exit handler
        atexit.register(self.disconnect)

    # tries i2c writing to the DMD multiple times
    def write_with_retry(self, reg, val, retry=3):
        self.log(logging.DEBUG, "Writing {} to DMD register {}".format(val, reg))
        if self.dmd is None:
            msg = "Can't write to DMD, no handle has been created!"
            self.log(logging.CRITICAL, msg)
            sys.exit(msg)
        success = False
        caught_exception = None
        for _ in range(retry):
            try:
                print('DMD write byte reg:{:#02x} val:{:#02x}'.format(reg, int(val)))
                # self.pi.i2c_write_byte_data(self.dmd, reg, int(val))
                self.bus.write_byte_data(self.dmd_addr, reg, int(val))
                success = True
                break
            except Exception as e:
                print(e)
                caught_exception = e
                time.sleep(1)                   # wait 1 second to retry
        if not success:
            self.log(logging.ERROR, "I2C write error in projector! {} sequential writes failed".format(retry))
            raise caught_exception

    # tries i2c reading from the DMD multiple times
    def read_with_retry(self, reg, retry=3):
        self.log(logging.DEBUG, "Reading DMD register {}".format(reg))
        if self.dmd is None:
            msg = "Can't read from DMD, no handle has been created!"
            self.log(logging.CRITICAL, msg)
            sys.exit(msg)
        success = False
        caught_exception = None
        for _ in range(retry):
            try:
                print('DMD read byte reg:{:#02x}'.format(int(reg)))
                old_result = self.pi.i2c_read_byte_data(self.dmd, int(reg))
                result = self.bus.read_byte_data(self.dmd_addr, int(reg))
                if old_result != result:
                    print("DMD READ MISMATCH !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    print('  old, new {}:{}, {}:{}'.format(type(old_result), old_result, type(result), result))
                success = True
                return result
            except Exception as e:
                print(e)
                caught_exception = e
                time.sleep(1)                   # wait 1 second to retry
        if not success:
            self.log(logging.ERROR, "I2C read error in projector! {} sequential reads failed".format(retry))
            raise caught_exception

    # start the i2c connection to the projector and setup the virtual screen
    def connect(self):
        self.screenThread.start()                               # start screen thread
        self.dmd = self.pi.i2c_open(self.bus_num, self.dmd_addr)  # connect to dmd via i2c
        time.sleep(self.I2C_IO_DELAY)
        self.led = self.pi.i2c_open(self.bus_num, self.led_addr) # connect to LED driver via i2c
        self.read_all_status()
        self.stop_sequencer()                                   # stop the dmd sequencer
        self.read_all_status()
        self.set_pixel_mode("Single")                           # set the default pixel mode
        self.read_all_status()
        self.set_video_source("HDMI")                           # set video source to HDMI
        self.read_all_status()
        time.sleep(5)                                           # must wait for at least 5 seconds to read or write display mode
        self.set_dmd_operation_mode("Video pattern mode")       # set to video pattern mode
        self.read_all_status()
        self.initialize_led_driver()
        # self.ledTempLimit = int(DEF_LED_TEMP_LIMIT/10)
        # self.boardTempLimit = DEF_BOARD_TEMP_LIMIT
        # self.ocpLimit = DEF_OCP_AMP
        self.set_led_amplitude(100)

    # cleanup and disconnect
    def disconnect(self):
        self.screenThread.stop()         # stop screen thread on exit
        if self.dmd is not None:
            self.stop_sequencer()        # make sure DMD is stopped on exit
            self.pi.i2c_close(self.dmd)
            self.dmd = None
        if self.led is not None:
            self.pi.i2c_close(self.led)
            self.led = None

    # Provides status information on the sequencer, digital micromirror device
    #    (DMD) controller, and initialization of DLPC900
    #    See "Hardware Status" in DLPC900 docs
    def readHardwareStatus(self):
        status = self.read_with_retry(TI_REG_R_HW_STATUS)
        return status

    # Provides the DLPC900 status on internal memory tests
    #    See "System Status" in DLPC900 docs
    def readSystemStatus(self):
        status = self.read_with_retry(TI_REG_R_SYS_STATUS)
        return status

    # Provides the status of DMD park and DLPC900 sequencer, frame buffer, and
    #    gamma correction
    #    See "Main Status" in DLPC900 docs
    def readMainStatus(self):
        status = self.read_with_retry(TI_REG_R_MAIN_STATUS)
        return status

    # Retrieves the error code number from the DLPC900 of the last executed command
    #    See "Read Error Code" in DLPC900 docs
    def readErrorCode(self):
        error = self.read_with_retry(TI_REG_R_ERROR_CODE)
        return convert_error_code(error)

    # read all status registers
    def read_all_status(self):
        self.log(logging.INFO, " Visitech status:")
        time.sleep(self.I2C_IO_DELAY)
        self.log(logging.INFO, "  System status:   {:#08b}".format(self.readSystemStatus()))
        time.sleep(self.I2C_IO_DELAY)
        self.log(logging.INFO, "  Hardware status: {:#08b}".format(self.readHardwareStatus()))
        time.sleep(self.I2C_IO_DELAY)
        self.log(logging.INFO, "  Main status:     {:#08b}".format(self.readMainStatus()))
        time.sleep(self.I2C_IO_DELAY)
        self.log(logging.INFO, "  Error code:      {}".format(self.readErrorCode()))
        time.sleep(self.I2C_IO_DELAY)

    def log(self, lvl, msg):
        try:
            self.logger.log(lvl, msg)
        except AttributeError:
            if lvl > 0:     # only print messages higher than DEBUG
                print(msg)

    def start_sequencer(self):
        self.log(logging.INFO, "Start sequencer")
        self.write_with_retry(TI_REG_W_SEQUENCE, TI_SEQUENCE_ON)
        time.sleep(self.I2C_IO_DELAY)

    def stop_sequencer(self):
        self.log(logging.INFO, "Stop sequencer")
        self.write_with_retry(TI_REG_W_SEQUENCE, TI_SEQUENCE_OFF)
        time.sleep(self.I2C_IO_DELAY)

    def pause_sequencer(self):
        self.log(logging.INFO, "Pause sequencer")
        self.write_with_retry(TI_REG_W_SEQUENCE, TI_SEQUENCE_PAUSE)
        time.sleep(self.I2C_IO_DELAY)

    def set_dmd_operation_mode(self, mode):
        # Set display mode. See 2.4.1 "Display Mode Selection" in DLPC900 Programmers Guide
        pattern_modes = {
            "Video mode"              : TI_DISPLAY_MODE_NORMAL,
            "Pre-stored pattern mode" : TI_DISPLAY_MODE_PRE_STORED,     # images from flash
            "Video pattern mode"      : TI_DISPLAY_MODE_VIDEO_PATTERN,
            "Pattern On-The-Fly mode" : TI_DISPLAY_MODE_ON_THE_FLY      # images loaded through USB/I2C
        }
        self.log(logging.INFO, "Set DMD operation mode to: {}".format(mode))
        if mode in pattern_modes.keys():
            self.write_with_retry(TI_REG_W_DISPLAY_MODE, pattern_modes[mode])
            time.sleep(self.I2C_IO_DELAY)
        else:
            self.log(logging.ERROR, "Bad video mode supplied: {}".format(mode))

    def set_video_source(self, source):
        # See 2.3.4.3 "IT6535 Power Mode" in DLPC900 Programmers Guide
        #
        # The IT6535 Power Mode command allows the user to power-down and tri-state the IT6535 digital receiver
        # data and sync outputs. This command is ignored if the IT6535 is not present or has been disabled in the
        # App Defaults Settings found in the DLP LightCrafter 6500 & 9000 GUI Firmware tab.

        video_sources = {
            "HDMI"        : TI_IT6536_HDMI,         # up to 30 Hz
            "DisplayPort" : TI_IT6536_DISPLAYPORT,  # up to 60 Hz
        }
        self.log(logging.INFO, "Set video source to: {}".format(source))
        if source in video_sources.keys():
            self.write_with_retry(TI_REG_W_IT6535, video_sources[source])
            time.sleep(self.I2C_IO_DELAY)
        else:
            self.log(logging.ERROR, "Bad video source supplied: {}".format(source))

    def set_pixel_mode(self, mode):
        #########################################################
        # Port and Clock Configuration
        #    See 2.3.3.1 "Port and Clock Configuration" in DLPC900 Programmers Guide
        #########################################################
        # This command selects which port the RGB data is on and which pixel clock, data enable, and syncs to
        # use. The user must select the correct port and clock configuration according to the PCB layout routing.

        # 1 byte
        #    bits 1:0 - pixel mode
        #        0 = Data Port 1, Single Pixel mode
        #        1 = Data Port 2, Single Pixel mode
        #        2 = Data Port 1-2, Dual Pixel mode. Even pixel on port 1, Odd pixel on port 2
        #        3 = Data Port 2-1, Dual Pixel mode. Even pixel on port 2, Odd pixel on port 1
        #    bits 3:2 - pixel clock
        #        0 = Pixel Clock 1
        #        1 = Pixel Clock 2
        #        2 = Pixel Clock 3
        #        3 = Reserved
        #    bit 4 - data enable
        #        0 = Data Enable 1
        #        1 = Data Enable 2
        #    bit 5 - vsync select
        #        0 = P1 VSync and P1 HSync
        #        1 = P2 VSync and P2 HSync

        pixel_modes = {
            "Single" : 0x0,
            "Dual"   : 0x2
        }
        self.log(logging.INFO, "Set pixel mode to: {}".format(mode))
        if mode in pixel_modes.keys():
            self.write_with_retry(TI_REG_W_PIXEL_MODE, pixel_modes[mode])
            time.sleep(self.I2C_IO_DELAY)
        else:
            self.log(logging.ERROR, "Bad pixel mode supplied: {}".format(mode))

    def setInternalImage(self, imageNum):
        '''imageNum range: 0 - 10'''
        self.log(logging.INFO, "Set internal image to number {}".format(imageNum))
        self.write_with_retry(TI_REG_W_DISPLAY_MODE, TI_DISPLAY_MODE_PRE_STORED)
        time.sleep(self.I2C_IO_DELAY)
        self.write_with_retry(TI_REG_W_TEST_PATTERN, imageNum)
        time.sleep(self.I2C_IO_DELAY)

    def set_sequencer_lut_definition(self, exposure, darktime=0, clear=1, bitdepth=7, wait_for_trigger=1, pattern_index=0, bit_index=0):
        #########################################################
        # Pattern Display LUT Definition
        #    See 2.4.4.3.4 "Pattern Display LUT Definition" in DLPC900 Programmers Guide
        #########################################################
        # The Pattern Display LUT Definition contains the definition of each pattern to be displayed during the
        # pattern sequence. Display Mode and Pattern Display LUT Configuration must be set before sending
        # any pattern LUT definition data. If the Pattern Display Data Input Source is set to streaming, the
        # image indexes do not need to be set. Regardless of the input source, the pattern definition must be set.

        self.log(logging.INFO, "Set sequencer LUT definition {} {} {} {} {} {} {}".format(exposure, darktime, clear, bitdepth, wait_for_trigger, pattern_index, bit_index))
        buf = list(range(12)) # an array of bytes to be sent to form this internal LUT entry in the DLPC900

        # pattern index (valid range 0 - 511)
        buf[0] = pattern_index & 0xff           # byte 0
        buf[1] = (pattern_index >> 8) & 0xff    # byte 1

        # exposure time
        #    bits 31:24 - reserved
        #    bits 23:0 - exposure time in microseconds
        temp = int(exposure)
        buf[2] = temp & 0xff            # byte 2
        buf[3] = (temp >> 8) & 0xff     # byte 3
        buf[4] = (temp >> 16) & 0xff    # byte 4

        # image settings (byte 5)
        temp = 0
        temp |= int(clear) & 0x1                    # bit 0 - clear the pattern after exposure. This is only applicable for 1 bit patterns
                                                    #    with an external trigger. For other patterns, the clear is automatically handled.
        temp |= (int(bitdepth) << 1) & 0x0e         # bits 1:3 - bit depth
                                                    #    b000 = 1 bit
                                                    #    b001 = 2 bit
                                                    #    b010 = 3 bit
                                                    #    ...
                                                    #    b111 = 8 bit
        color = 1
        temp |= (int(color) << 4) & 0x70            # bits 4:6 - color - in the Wintech, the LED is on the blue channel, in the Visitech it is on red
                                                    #    b000 = All LEDs disabled
                                                    #    b001 = Red
                                                    #    b010 = Green
                                                    #    b011 = Yellow (Green + Red)
                                                    #    b100 = Blue
                                                    #    b101 = Magenta (Blue + Red)
                                                    #    b110 = Cyan (Blue + Green)
                                                    #    b111 = White (Blue + Green + Red)
        temp |= (int(wait_for_trigger) << 7) & 0x80 # bit 7 - trigger/VSYNC
                                                    #    1 = Wait for trigger before displaying the pattern
                                                    #    0 = Continue running after previous pattern
        buf[5] = int(temp)                          # save byte 5

        # dark wait time
        #     bits 31:24 - reserved,
        #     bits 23:0 - dark display time following the exposure (in micro seconds))
        temp = int(darktime)
        buf[6] = temp & 0xff            # byte 6
        buf[7] = (temp >> 8) & 0xff     # byte 7
        buf[8] = (temp >> 16) & 0xff    # byte 8

        # trigger 2
        buf[9] = 0  # byte 9
                    # bit 0 - trigger 2 setting
                    #    1 = Disable trigger 2 output for this pattern
                    #    0 = Enable trigger 2 output for this pattern
                    # bits 1:7 - reserved

        # image pattern settings
        #    bits 10:0 - Image pattern index (Not applicable in video pattern mode) Valid Range 0-255
        #    bits 115:11 - Bit position in the image pattern (Frame in video pattern mode) Valid range 0-23
        buf[10] = 0                                 # byte 10
        buf[11] = int((bit_index & 0x1f) << 3)      # byte 11

        # send LUT to DLPC900
        data = [TI_REG_W_PATTERN_DISPLAY_LUT] + buf
        # data = [TI_REG_W_PATTERN_DISPLAY_LUT] + buf
        print('DMD write device val:{}'.format(data))
        print(bytearray(data))
        print('DMD write device val:{}'.format(buf))
        print(bytearray(buf))
        # self.pi.i2c_write_device(self.dmd, data)
        self.bus.write_i2c_block_data(self.dmd_addr, TI_REG_W_PATTERN_DISPLAY_LUT, bytearray(buf))
        time.sleep(0.01)

    def set_sequencer_lut_config(self, num_sequences=1, repeats=1):
        #########################################################
        # Pattern Display LUT Configuration
        #    See 2.4.4.3.3 "Pattern Display LUT Configuration" in DLPC900 Programmer's Guide
        #########################################################
        # The Pattern Display LUT Configuration command controls the execution of patterns stored in the lookup
        # table (LUT). Before executing this command, stop the current pattern sequence.

        # format the config command
        #   5 bytes total
        #   bytes 1:0
        #      bits 10:0 - Number of LUT entries (range 0 through 511)
        #         0 = Zero entries
        #         1 = One entries
        #         ...
        #         512 = 512 entries
        #   bytes 5:2 - Number of times to repeat the pattern sequence
        #               0 = repeat forever

        self.log(logging.INFO, "Set sequencer LUT config to: {} sequences, {} repeats".format(num_sequences, repeats))

        self.stop_sequencer() # current pattern must be stopped before writing config

        numPatternsByte = int(num_sequences).to_bytes(2, byteorder='little')
        repeats = int(repeats).to_bytes(4, byteorder='little')
        addr = TI_REG_W_PATTERN_DISPLAY_LUT_CONFIG.to_bytes(1, byteorder='little')

        # data = addr + numPatternsByte + repeats
        data = numPatternsByte + repeats
        print('DMD write device val:{}'.format(data))
        # self.pi.i2c_write_device(self.dmd, data)
        self.bus.write_i2c_block_data(self.dmd_addr, TI_REG_W_PATTERN_DISPLAY_LUT_CONFIG, bytearray(data))
        time.sleep(self.I2C_IO_DELAY)

    ###################################
    # Visitech LED and PCB board settings
    ###################################
    def writeLedParam(self, register, param):
        register = int(register).to_bytes(2, byteorder='big')
        param = int(param).to_bytes(4, byteorder='big')
        data = register + param
        print('LED write device val:{}'.format(data))
        # self.pi.i2c_write_device(self.led, data)
        self.bus.write_i2c_block_data(self.led_addr, register, bytearray(param))
        time.sleep(self.I2C_IO_DELAY)

    def readLedParam(self, register):
        register = int(register).to_bytes(4, byteorder='big')
        # print('LED write device val:{}'.format(register))
        self.pi.i2c_write_device(self.led, register)
        # self.bus.write_block_data(self.led_addr, 0, bytearray(register))
        time.sleep(self.I2C_IO_DELAY)
        print('LED read device 4 bytes')
        _, old_data = self.pi.i2c_read_device(self.led, 4)
        data = self.bus.read_i2c_block_data(self.led_addr, register, 4)

        if data != old_data:
            print("LED READ MISMATCH !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print('  old, new {}:{}, {}:{}'.format(type(old_data), old_data, type(data), data))

        # self.bus.read_block_data(self.led_addr, 0, ))
        # data = self.bus.read_i2c_block_data(self.led_addr, register, 4)
        time.sleep(self.I2C_IO_DELAY)
        # data is a `bytearray` object
        return int.from_bytes(data, byteorder='big')

    def initialize_led_driver(self):
        self.writeLedParam(LED_PWM_KEEP_OFF_REGISTER, DEF_PWM_KEEP_OFF)
        self.writeLedParam(LED_PFACTOR_REGISER, DEF_PFACTOR)
        self.writeLedParam(LED_IFACTOR_REGISTER, DEF_IFACTOR)
        self.writeLedParam(LED_LED_TEMP_LIMIT_REGISTER, DEF_LED_TEMP_LIMIT)
        self.writeLedParam(LED_BOARD_TEMP_LIMIT_REGISTER, DEF_BOARD_TEMP_LIMIT)
        self.writeLedParam(LED_OCPVALUE_REGISTER, round(DEF_OCP_AMP / OCP_AMP_PER_UNIT_HW_VER1))
        self.writeLedParam(LED_OPPVALUE_REGISTER, DEF_OPP_HW_VER_1)

    def set_led_amplitude(self, val):
        '''range: 0 - 1000'''
        self.log(logging.INFO, "Set LED amplitude to: {}".format(val))
        if val > 1000 or val < 0:
            self.log(logging.ERROR, "LED amplitude {} out of range")
            val = 100
        self.writeLedParam(LED_AMPLITUDE_REGISTER, val)
        self.writeLedParam(LED_SV_UPDATE_REGISTER, 1)
        self.writeLedParam(LED_SV_UPDATE_REGISTER, 0)
        self.ledPower = val

    def setLedTempLimit(self, limit):
        # self.ledTempLimit = int(limit)
        self.writeLedParam(LED_LED_TEMP_LIMIT_REGISTER, int(limit))

    def getLedTempLimit(self):
        self.log(logging.INFO, self.readLedParam(LED_LED_TEMP_LIMIT_REGISTER))

    def setBoardTempLimit(self, limit):
        # self.boardTempLimit = int(limit)
        self.writeLedParam(LED_BOARD_TEMP_LIMIT_REGISTER, int(limit))

    def setOcpLimit(self, limit):
        # self.ocpLimit = round(limit/OCP_AMP_PER_UNIT_HW_VER1)
        self.writeLedParam(LED_OCPVALUE_REGISTER, round(limit/OCP_AMP_PER_UNIT_HW_VER1))

    def getBoardTemp(self):
        boardTemp = self.readLedParam(LED_BOARDTEMP_REGISTER) / 256
        self.log(logging.INFO, "Board temperature: {:.1f}".format(boardTemp))
        # self.log(("Board temperature: {:.1f}".format(self.boardTemp))

    def getLedTemp(self):
        ledTemp = self.readLedParam(LED_LEDTEMP_REGISTER) / 10
        self.log(logging.INFO, "LED temperature: {:.1f}".format(ledTemp))

    # # Sticky bits: (4):OCP (3): Door_open (2): Fan stopped (1): Board_overtemp, (0): LED_overtemp
    # these don't appear to be correct
    def getStickyBits(self):
        stickybits = self.readLedParam(LED_STICKYBITS_REGISTER)
        self.log(logging.INFO, "Sticky bits: {0:b}".format(stickybits))

    ###################################
    # Higher level functions
    ###################################

    def split_exposure_time(self, exposure):
        """
        Split a long exposure time into an array of smaller exposure times.
        """
        n = int(exposure // self.max_exp_time)
        if exposure % self.max_exp_time != 0:
            exposure = [self.max_exp_time] * n + [exposure % self.max_exp_time]
        else:
            exposure = [self.max_exp_time] * n
        return exposure

    def clear_image(self):
        """
        Blank the virtual screen that provides the image to the projector.
        Sets full image to black.
        """
        self.screenThread.screen.clear()

    def project(self, image, exposure, power, repeats=1):
        """
        Call all of the necessary methods to project an image, and block until projection
        is complete.
        """
        self.log(logging.INFO, "Exposing {} for {} ms at power {}".format(image, exposure, power))
        self.set_led_amplitude(power)
        self.screenThread.screen.draw(image)                    # draw to the virtual screen
        if repeats == 0:    # if continuous display is desired
            self.set_sequencer_lut_definition(exposure*1000, 0, 0, 7, 0, 0, 0)  # this provides the minimum blanking of 233 us of the full 33333 us cycle (at 30Hz on HDMI)
            self.set_sequencer_lut_config(repeats=repeats)                      # 0 means repeat forever
            self.start_sequencer()                                              # start the sequencer and don't stop it (will be stopped on program exit)
        else:               # normal display is desired
            for t in self.split_exposure_time(exposure):
                self.set_sequencer_lut_definition(exposure=t*1000)      # the TI board expects exposure in microseconds
                self.set_sequencer_lut_config(repeats=repeats)          # set the number of repetitions
                self.read_all_status()
                time.sleep(0.1)
                self.start_sequencer()                                  # start the sequencer
                self.read_all_status()
                time.sleep(0.1 + t * 1e-3)                              # wait for the exposure time with a little wiggle room
                self.stop_sequencer()                                   # stop the sequencer
                self.read_all_status()

    def projectMulti(self, images, exposureTimes, ledPowers):
        """Project multiple images with its own expoure time and
        and LED power setting.
        :param list images: a list of image filenames
        :param list exposureTimes: a list of exposure times (ms)
        :param list ledPowers: a list of led power settings
                            (0-1000)
        """
        for image, expTime, power in zip(images, exposureTimes, ledPowers):
            self.project(image, expTime, power)

if __name__ == '__main__':
    projectorResolution = (2560, 1600)
    p = Projector(projectorResolution)
    p.connect()
    p.getLedTemp()
    p.getLedTempLimit()
    p.getBoardTemp()
    p.project("images/calibrate.png", exposure=1000, power=100)
    p.read_all_status()
    p.project("images/visitech_1.png", exposure=500, power=100)
    p.read_all_status()
    p.project("images/visitech_2.png", exposure=500, power=100)
    p.read_all_status()
    p.project("images/visitech_3.png", exposure=500, power=100)
    p.read_all_status()
    p.project("images/visitech_4.png", exposure=500, power=100)
    p.read_all_status()
    p.screenThread.stop()
    print("Done")
