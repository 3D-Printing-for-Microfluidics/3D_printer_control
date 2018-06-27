# -*- coding: utf-8 -*-
"""Light engine I2C module for Raspberry Pi"""
import logging
import time

from .constants import *
from .errors import *


class LightEngineI2C:

    def __init__(self, pi=None, bus=1, logger=None):
        self.pi = pi
        self.bus = bus
        self.logger = logger

    def init_pi(self, pi):
        self.pi = pi

    def connect(self):
        self.dmd = self.pi.i2c_open(self.bus, TI_I2C_RADDR>>1)
        self.led = self.pi.i2c_open(self.bus, LED_I2C_WADDR>>1)

        self.stop()
        self.setPixelMode(0)
        self.setVideoInput(0)
        self.initDisplayMode()

        self.initLedDriver()
        self.ledTempLimit = int(DEF_LED_TEMP_LIMIT/10)
        self.boardTempLimit = DEF_BOARD_TEMP_LIMIT
        self.ocpLimit = DEF_OCP_AMP

        self.setLedAmplitude(100)

    def log(self, lvl, msg):
        try:
            self.logger.log(lvl, msg)
        except AttributeError:
            print(msg)

    def start(self):
        self.pi.i2c_write_byte_data(
            self.dmd, 
            TI_REG_W_SEQUENCE, 
            TI_SEQUENCE_ON
        )

    def stop(self):
        self.pi.i2c_write_byte_data(
            self.dmd, 
            TI_REG_W_SEQUENCE, 
            TI_SEQUENCE_OFF
        )

    def pause(self):
        self.pi.i2c_write_byte_data(
            self.dmd, 
            TI_REG_W_SEQUENCE, 
            TI_SEQUENCE_PAUSE
        )

    def initDisplayMode(self):
        time.sleep(5) # must wait for at least 5 s to read or write display mode
        mode = self.pi.i2c_read_byte_data(self.dmd, TI_REG_R_DISPLAY_MODE)
        if mode == 0: # Normal video mode, need to initialize to video pattern mode
            self.setDisplayMode(0) # set to video pattern mode

    def setDisplayMode(self, mode):
        '''Set display mode. 

        :param int mode:
        0: video pattern mode; 1: normal video mode;
        2: pre-stored mode; 3: on-the-fly mode.
        '''
        patternModes = [TI_DISPLAY_MODE_VIDEO_PATTERN, 
                        TI_DISPLAY_MODE_NORMAL, 
                        TI_DISPLAY_MODE_PRE_STORED, 
                        TI_DISPLAY_MODE_ON_THE_FLY]
        self.pi.i2c_write_byte_data(
            self.dmd, 
            TI_REG_W_DISPLAY_MODE, 
            patternModes[mode]
        )

    def setVideoInput(self, input):
        """Set video source. 
        The Visitech LRS-WQ light engine has a HDMI and a 
        DisplayPort connection. They support different frame 
        rate, HDMI 2560x1600 @30Hz and DisplayPort 2560x1600 
        @60Hz.

        :param int input: either 0 or 1. 0 - HDMI; 1 - DisplayPort.
        """
        inputSources = [TI_IT6536_HDMI, TI_IT6536_DISPLAY]
        self.pi.i2c_write_byte_data(
            self.dmd, 
            TI_REG_W_IT6535, 
            inputSources[input]
        )

    def setPixelMode(self, mode):
        '''0: single; 1: dual.'''
        pixelModes = [0x0, 0x2]
        self.pi.i2c_write_byte_data(
            self.dmd, 
            TI_REG_W_PIXEL_MODE, 
            pixelModes[mode]
        )

    def setInternalImage(self, imageNum):
        '''imageNum range: 0 - 10'''
        self.pi.i2c_write_byte_data(
            self.dmd, 
            TI_REG_W_DISPLAY_MODE, 
            TI_DISPLAY_MODE_PRE_STORED
        )
        self.pi.i2c_write_byte_data(
            self.dmd, 
            TI_REG_W_TEST_PATTERN, 
            imageNum
        )

    def parseSendSequence(self, sequence, repeat):
        assert [len(l) for l in sequence] == [len(sequence[0])] * len(sequence)
        if len(sequence[0]) != NUM_SEQUENCE_COMMAND_VAR:
            self.log(logging.ERROR, "The number of parameters is not right.")
            return ERROR_SEQUENCE_NUM_ARGS
        numPattern = len(sequence)
        if numPattern > MAX_NUM_PATTERNS_IN_SEQ:
            self.log(logging.ERROR, "Too many patterns")
            return ERROR_SEQUENCE_TO_MANY_PATTERNS
        if len(sequence) == 0:
            self.log(logging.ERROR, "No line is found.")
            return ERROR_COULD_NOT_FIND_ANY_LINES_IN_SEQUENCE_FILE
        # write sequence
        for i in range(numPattern):
            buf = list(range(12))
            # pattern index
            buf[0] = i & 0xff
            buf[1] = (i >> 8) & 0xff
            # exposure time
            temp = int(sequence[i][0])
            buf[2] = temp & 0xff
            buf[3] = (temp >> 8) & 0xff
            buf[4] = (temp >> 16) & 0xff
            temp = 0
            temp |= (int(sequence[i][1]) << 1) & 0x0e   # bit depth
            temp |= (int(sequence[i][2]) << 4) & 0x70   # color
            temp |= (int(sequence[i][3]) << 7) & 0x80   # trigger/VSYNC
            temp |= int(sequence[i][6]) & 0x1           # clear image
            buf[5] = int(temp)
            # dark wait time
            temp = int(sequence[i][4])
            buf[6] = temp & 0xff
            buf[7] = (temp >> 8) & 0xff
            buf[8] = (temp >> 16) & 0xff
            buf[9] = 0                                  # trigger 2
            buf[10] = 0                                 # ???
            buf[11] = int((sequence[i][5] & 0x1f) << 3) # ???????
            self.pi.i2c_write_device(
                self.dmd, 
                [TI_REG_W_PATTERN_DISPLAY_LUT] + buf
            )
            time.sleep(0.01)
            
        # write config
        numPattern = int(numPattern).to_bytes(2, byteorder='little')
        repeat = int(repeat).to_bytes(4, byteorder='little')
        addr = TI_REG_W_PATTERN_DISPLAY_LUT_CONFIG.to_bytes(1, byteorder='little')
        self.pi.i2c_write_device(
            self.dmd, 
            addr + numPattern + repeat
        )

    def getSequencerStatus(self):
        seqstat = self.pi.i2c_read_byte_data(
            self.led, 
            TI_REG_R_MAIN_STATUS
        )
        self.log(logging.INFO, "Sequencer status: {}".format(seqstat))

    ###################################
    # LED and PCB board settings
    ###################################
    def writeLedParam(self, register, param):
        register = int(register).to_bytes(4, byteorder='big')
        param = int(param).to_bytes(4, byteorder='big')
        self.pi.i2c_write_device(self.led, register+param)
        time.sleep(0.01)

    def readLedParam(self, register):
        # TODO: check read result format
        register = int(register).to_bytes(4, byteorder='big')
        self.pi.i2c_write_device(self.led, register)
        count, data = self.pi.i2c_read_device(self.led, 4)
        # data is a `bytearray` object
        return int.from_bytes(data, byteorder='big')

    def initLedDriver(self):
        # Default values are defined in header/constants.py
        self.writeLedParam(LED_PWM_KEEP_OFF_REGISTER, DEF_PWM_KEEP_OFF)
        self.writeLedParam(LED_PFACTOR_REGISER, DEF_PFACTOR)
        self.writeLedParam(LED_IFACTOR_REGISTER, DEF_IFACTOR)
        self.writeLedParam(LED_LED_TEMP_LIMIT_REGISTER, DEF_LED_TEMP_LIMIT)
        self.writeLedParam(LED_BOARD_TEMP_LIMIT_REGISTER, DEF_BOARD_TEMP_LIMIT)
        self.writeLedParam(LED_OCPVALUE_REGISTER, 
                           round(DEF_OCP_AMP / OCP_AMP_PER_UNIT_HW_VER1))
        self.writeLedParam(LED_OPPVALUE_REGISTER, DEF_OPP_HW_VER_1)

    def setLedAmplitude(self, val):
        '''range: 0 - 1000'''
        if val > 1000 or val < 0:
            self.log(logging.ERROR, "LED amplitude out of range")
            val = 100
        self.writeLedParam(LED_AMPLITUDE_REGISTER, val)
        self.writeLedParam(LED_SV_UPDATE_REGISTER, 1)
        self.writeLedParam(LED_SV_UPDATE_REGISTER, 0)
        self.ledPower = val

    def setLedTempLimit(self, limit):
        self.ledTempLimit = int(limit)
        self.writeLedParam(LED_LED_TEMP_LIMIT_REGISTER, self.ledTempLimit*10)

    def setBoardTempLimit(self, limit):
        self.boardTempLimit = int(limit)
        self.writeLedParam(LED_BOARD_TEMP_LIMIT_REGISTER, self.boardTempLimit)
        
    def setOcpLimit(self, limit):
        self.ocpLimit = round(limit/OCP_AMP_PER_UNIT_HW_VER1)
        self.writeLedParam(LED_OCPVALUE_REGISTER, self.ocpLimit)

    def getBoardTemp(self):
        self.boardTemp = self.readLedParam(LED_BOARDTEMP_REGISTER) / 256
        self.log(logging.INFO, "Board temperature: {.1f}".format(self.boardTemp))

    def getLedTemp(self):
        self.ledTemp = self.readLedParam(LED_LEDTEMP_REGISTER) / 10
        self.log(logging.INFO, "LED temperature: {.1f}".format(self.ledTemp))

    def getStickyBits(self):
        self.stickybits = self.readLedParam(LED_STICKYBITS_REGISTER)
        self.log(logging.INFO, "Sticky bits: {}".format(self.stickybits))

    def getHelp(self):
        print("Arguments:")
        print("start\t\t- Start the sequencer")
        print("stop\t\t- Stop the sequencer")
        print("pause\t\t- Pause the sequencer")
        print("video\t\t- Turn on video pattern mode")
        print("internal imageNum\t- Turn on internal image demo")
        print("init interface\t\t- Activates hdmi or displayport interface and video pattern mode in one command. interface dp will activate display port. Everything else will activate hdmi")
        print("pixelmode mode\t\t- Activates single or dual pixel mode. mode dual will activate dual pixel mode. Everything else will activate single pixel mode")
        print("upload\tfilename\trepeat\t- Uploads sequence file filename and prepares to run it repeat times. A repeat value of 0 will run the sequence in a loop")
        print("initled\t\t\t- Inits and tweaks LED ocp/opp/temp limits and current regulation parametres")
        print("setamplitude value\t\t- Sets the led amplitude to the given value")
        print("boardtemp\t\t\t- Reads the led board temperature")
        print("ledtemp\t\t\t- Reads the led temperature")
        print("sticky\t\t\t- Reads the sticky bits")
        print("seqstatus- Reads the status of the sequencer, returned bit 1 shows sequencer status")
        print("setledtemplimit limit\t\t- Sets the led temperature limit. Temp in Celsius equals limit devided by 10")
        print("setboardtemplimit limit\t\t- Sets the board temperature limit. Temp in Celsius equals limit")
        print("ocplimit limit\t\t- Sets the board ocp limit in Ampere.")
        print("help\t\t- Shows this readme")
