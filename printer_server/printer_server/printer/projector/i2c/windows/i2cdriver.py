from .header import *
from ctypes import *
import time


__all__ = ['LightEngineBase', 'LightEngineI2C']

DLN = cdll.dln
dlnWrite = DLN.DlnI2cMasterWrite
dlnWrite.argtypes = [HDLN, c_uint8, c_uint8, c_uint8, c_uint32, c_uint16, POINTER(c_uint8)]
dlnWrite.restypes = [DLN_RESULT]
dlnRead = DLN.DlnI2cMasterRead
dlnRead.argtypes = [HDLN, c_uint8, c_uint8, c_uint8, c_uint32, c_uint16, POINTER(c_uint8)]
dlnRead.restypes = [DLN_RESULT]

class LightEngineBase:
    
    _ok = ERROR_OK
    
    def __init__(self):
        self._handle = HDLN_INVALID_HANDLE
        
        self.i2cPortNum = 0
        self.i2cFrequency = 100000
        
        self.connectServer()
        
    def i2cInit(self):
        result = DLN.DlnConnect(create_string_buffer(b"localhost"), DLN_DEFAULT_SERVER_PORT)
        time.sleep(0.01)
        if not DLN_SUCCEEDED(result):
            print("I2C initialization failed (%s)" % hex(result))
            self.disconnectServer()
            return ERROR_DLN_SERVER_CONNECT_FAILED
        else:
            print("I2C initialization OK (%s)" % hex(result))
            return ERROR_OK
            
    def openDevice(self):
        if self._handle.value != HDLN_INVALID_HANDLE.value:
            DLN.DlnCloseHandle(self._handle)
            self._handle = HDLN_INVALID_HANDLE
        result = DLN.DlnOpenDevice(c_uint32(0), byref(self._handle))
        time.sleep(0.01)
        if DLN_FAILED(result):
            print("Open device failed (%s)" % hex(result))
            self.disconnectServer()
            return ERROR_DLN_ADAPTER_OPEN
        else:
            print("Open device OK (%s)" % hex(result))
            return ERROR_OK
            
    def setI2cMaster(self):
        conflict = c_uint16()
        result = DLN.DlnI2cMasterEnable(self._handle, c_uint8(self.i2cPortNum), byref(conflict))
        time.sleep(0.01)
        if DLN_FAILED(result):
            print("I2C master enable failed (%s)" % hex(result))
            self.disconnectServer()
            return ERROR_MASTER_ENABLE_FAILED
        else:
            print("I2C master enabled OK (%s)" % hex(result))
            return ERROR_OK
            
    def connectServer(self):
        self.i2cInit()
        self.openDevice()
        self.setI2cMaster()
        
    def disconnectServer(self):
        DLN.DlnDisconnectAll()
        return ERROR_OK
        
    def write(self, slaveAddr, memAddr, memAddrLen, data, dataSize):
        time.sleep(0.01)
        writeData = (c_uint8 * dataSize)()
        writeData[:] = data.to_bytes(dataSize, byteorder="big") # [:] keep writeData to c_ubyte_Array
        if len(writeData) == 0:
            print("No data to write")
            return ERROR_INVALID_WRITE_DATA
        result = dlnWrite(self._handle, self.i2cPortNum, slaveAddr>>1, 
                          memAddrLen, memAddr, dataSize, writeData)
        if DLN_FAILED(result):
            print("Write data failed (%s)" % hex(result))
            return ERROR_WRITE_FAILED
        return ERROR_OK
    
    def read(self, slaveAddr, memAddr, memAddrLen, data, dataSize):
        time.sleep(0.01)
        readData = (c_uint8 * dataSize)()
        result = dlnRead(self._handle, self.i2cPortNum, slaveAddr>>1, 
                         memAddrLen, memAddr, dataSize, readData)
        result = DLN_RESULT(result).value # result has be to converted to c_uint16 first
        if DLN_FAILED(result):
            print("Read data failed (%s)" % hex(result))
            return ERROR_READ_FAILED
        data[:] = readData
        return ERROR_OK
    
    def parseSendSequence(self, sequence, repeat):
        assert [len(l) for l in sequence] == [len(sequence[0])] * len(sequence)
        if len(sequence[0]) != NUM_SEQUENCE_COMMAND_VAR:
            print("The number of parameters is not right.")
            return ERROR_SEQUENCE_NUM_ARGS
        numPattern = len(sequence)
        if numPattern > MAX_NUM_PATTERNS_IN_SEQ:
            print("Too many patterns")
            return ERROR_SEQUENCE_TO_MANY_PATTERNS
        if len(sequence) == 0:
            print("No line is found.")
            return ERROR_COULD_NOT_FIND_ANY_LINES_IN_SEQUENCE_FILE
        # write sequence
        for i in range(numPattern):
            buf = (c_uint8 * 12)()
            buf[0:2] = int(i).to_bytes(2, byteorder='little') # pattern index
            buf[2:5] = int(sequence[i][0]).to_bytes(3, byteorder='little') # exposure time
            temp = 0
            temp |= (int(sequence[i][1]) << 1) & 0x0e        # bit depth
            temp |= (int(sequence[i][2]) << 4) & 0x70        # color
            temp |= (int(sequence[i][3]) << 7) & 0x80        # trigger/VSYNC
            temp |= int(sequence[i][6]) & 0x1              # clear image
            buf[5] = int(temp)
            buf[6:9] = int(sequence[i][4]).to_bytes(3, byteorder='little') # dark wait time
            buf[9] = 0                                  # trigger 2
            buf[10] = 0                                 # ???
            buf[11] = int(((sequence[i][5]) & 0x1f) << 3)   # ???????
            result = dlnWrite(self._handle, self.i2cPortNum, TI_I2C_RADDR>>1, 
                              1, TI_REG_W_PATTERN_DISPLAY_LUT, 12, buf)
            if DLN_FAILED(result):
                print("Write sequence failed (%s)" % hex(result))
                return ERROR_WRITE_FAILED
            time.sleep(0.01)
            
        # write config
        bufconfig = (c_uint8 * 6)()
        bufconfig[0:2] = numPattern.to_bytes(2, byteorder='little')
        bufconfig[2:] = int(repeat).to_bytes(4, byteorder='little')
        result = dlnWrite(self._handle, self.i2cPortNum, TI_I2C_RADDR>>1, 
                          1, TI_REG_W_PATTERN_DISPLAY_LUT_CONFIG, 6, bufconfig)
        if DLN_FAILED(result):
            print("Write config failed (%s)" % hex(result))
            return ERROR_WRITE_FAILED
            
        return ERROR_OK
        
    def initLedDriver(self):
        # Default values are defined in header/constants.py
        
        ret = self.writeLedParam(param = DEF_PWM_KEEP_OFF, memAddr = LED_PWM_KEEP_OFF_REGISTER)
        if ret != ERROR_OK:
            return ret
        ret = self.writeLedParam(param = DEF_PFACTOR, memAddr = LED_PFACTOR_REGISER)
        if ret != ERROR_OK:
            return ret
        ret = self.writeLedParam(param = DEF_IFACTOR, memAddr = LED_IFACTOR_REGISTER)
        if ret != ERROR_OK:
            return ret
        ret = self.writeLedParam(param = DEF_LED_TEMP_LIMIT, memAddr = LED_LED_TEMP_LIMIT_REGISTER)
        if ret != ERROR_OK:
            return ret
        ret = self.writeLedParam(param = DEF_BOARD_TEMP_LIMIT, memAddr = LED_BOARD_TEMP_LIMIT_REGISTER)
        if ret != ERROR_OK:
            return ret
        
        ret = self.writeLedParam(param = round(DEF_OCP_AMP / OCP_AMP_PER_UNIT_HW_VER1), 
                                 memAddr = LED_OCPVALUE_REGISTER)
        if ret != ERROR_OK:
            return ret
        ret = self.writeLedParam(param = DEF_OPP_HW_VER_1, memAddr = LED_OPPVALUE_REGISTER)
        if ret != ERROR_OK:
            return ret
            
    def writeLedParam(self, param, memAddr):
        sendbyte = (c_uint8 * 4)()
        sendbyte[:] = int(param).to_bytes(4, byteorder="big")
        result = dlnWrite(self._handle, self.i2cPortNum, LED_I2C_WADDR>>1, 
                          2, memAddr, 4, sendbyte)
        time.sleep(0.01)
        if DLN_FAILED(result):
            print("Write LED parameters failed (%s)" % hex(result))
            self.disconnectServer()
        else:
            return ERROR_OK

            
class LightEngineI2C(LightEngineBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        time.sleep(0.01)
        self.stop()
        self.setPixelMode(0)
        self.setVideoInput(0)
        self.initDisplayMode()

        self.initLedDriver()
        self.ledTempLimit = int(DEF_LED_TEMP_LIMIT/10)
        self.boardTempLimit = DEF_BOARD_TEMP_LIMIT
        self.ocpLimit = DEF_OCP_AMP

        self.setLedAmplitude(100)
        
    def start(self):
        ret = self.write(TI_I2C_RADDR, TI_REG_W_SEQUENCE, 1, TI_SEQUENCE_ON, 1)
        if ret != ERROR_OK:
            self.disconnectServer()
        return ret
            
    def stop(self):
        ret = self.write(TI_I2C_RADDR, TI_REG_W_SEQUENCE, 1, TI_SEQUENCE_OFF, 1)
        if ret != ERROR_OK:
            self.disconnectServer()
        return ret
            
    def pause(self):
        ret = self.write(TI_I2C_RADDR, TI_REG_W_SEQUENCE, 1, TI_SEQUENCE_PAUSE, 1)
        if ret != ERROR_OK:
            self.disconnectServer()
        return ret
    
    def initDisplayMode(self):
        time.sleep(5) # must wait for at least 5 s to read or write display mode
        mode = (c_uint8 * 1)()
        self.read(TI_I2C_RADDR, TI_REG_R_DISPLAY_MODE, 1, mode, 1)
        if mode[0] == 0: # Normal video mode, need to initialize to video pattern mode
            self.setDisplayMode(0) # set to video pattern mode

    def setDisplayMode(self, mode):
        '''
        0: video pattern mode; 1: normal video mode;
        2: pre-stored mode; 3: on-the-fly mode.
        '''
        # In C++ source code, display mode is set to normal video mode prior to video pattern mode.
        # It is not necessary.

        # ret = self.write(TI_I2C_RADDR, TI_REG_W_DISPLAY_MODE, 1, TI_DISPLAY_MODE_NORMAL, 1)
        # if ret != ERROR_OK:
        #     self.disconnectServer()
        #     return ret
        # time.sleep(0.1)
        patternModes = [TI_DISPLAY_MODE_VIDEO_PATTERN, TI_DISPLAY_MODE_NORMAL, 
                       TI_DISPLAY_MODE_PRE_STORED, TI_DISPLAY_MODE_ON_THE_FLY]
        ret = self.write(TI_I2C_RADDR, TI_REG_W_DISPLAY_MODE, 1, patternModes[mode], 1)
        if ret != ERROR_OK:
            self.disconnectServer()
        return ret
        
    def setVideoInput(self, input):
        '''0: HDMI; 1: DisplayPort.'''
        inputSources = [TI_IT6536_HDMI, TI_IT6536_DISPLAY]
        ret = self.write(TI_I2C_RADDR, TI_REG_W_IT6535, 1, inputSources[input], 1)
        if ret != ERROR_OK:
            self.disconnectServer()
        return ret
        
    def setPixelMode(self, mode):
        '''0: single; 1: dual.'''
        pixelModes = [0x0, 0x2]
        ret = self.write(TI_I2C_RADDR, TI_REG_W_PIXEL_MODE, 1, pixelModes[mode], 1)
        if ret != ERROR_OK:
            self.disconnectServer()
        return ret
        
    def setInternalImage(self, imageNum):
        '''imageNum range: 0 - 10'''
        ret = self.write(TI_I2C_RADDR, TI_REG_W_DISPLAY_MODE, 1, TI_DISPLAY_MODE_PRE_STORED, 1)
        if ret != ERROR_OK:
            self.disconnectServer()
            return ret
        
        ret = self.write(TI_I2C_RADDR, TI_REG_W_TEST_PATTERN, 1, imageNum, 1)
        if ret != ERROR_OK:
            self.disconnectServer()
        return ret
        
    def setLedAmplitude(self, val):
        '''range: 0 - 1000'''
        if val > 1000 or val < 0:
            self.disconnectServer
            print("LED amplitude out of range")
            return ERROR_TO_HIGH_LED_AMPLITUDE
        # ret = self.writeLedParam(param = val, memAddr = LED_AMPLITUDE_REGISTER)
        ret = self.write(LED_I2C_WADDR, LED_AMPLITUDE_REGISTER, 2, val, 4)
        if ret != ERROR_OK:
            self.disconnectServer()
            return ret
        sendbyte = 1
        ret = self.write(LED_I2C_WADDR, LED_SV_UPDATE_REGISTER, 2, sendbyte, 4)
        if ret != ERROR_OK:
            self.disconnectServer()
            return ret
        sendbyte = 0
        ret = self.write(LED_I2C_WADDR, LED_SV_UPDATE_REGISTER, 2, sendbyte, 4)
        if ret != ERROR_OK:
            self.disconnectServer()
        self.ledPower = val
        return ret
        
    def getBoardTemp(self):
        t = (c_uint8 * 4)()
        ret = self.read(LED_I2C_WADDR, LED_BOARDTEMP_REGISTER, 2, t, 4)
        if ret != ERROR_OK:
            self.disconnectServer()
            return ret
        self.boardTemp = (int.from_bytes(t, byteorder='big', signed=False))/256
        print("Board temperature: %.1f" % self.boardTemp)
        return ret
        
    def getLedTemp(self):
        t = (c_uint8 * 4)()
        ret = self.read(LED_I2C_WADDR, LED_LEDTEMP_REGISTER, 2, t, 4)
        if ret != ERROR_OK:
            self.disconnectServer()
            return ret
        self.ledTemp = (int.from_bytes(t, byteorder='big', signed=False))/10
        print("LED temperature: %.1f" % self.ledTemp)
        return ret
        
    def getStickyBits(self):
        stickybits = (c_uint8 * 4)()
        ret = self.read(LED_I2C_WADDR, LED_STICKYBITS_REGISTER, 2, stickybits, 4)
        if ret != ERROR_OK:
            self.disconnectServer()
            return ret
        self.stickybits = int.from_bytes(t, byteorder='big', signed=False)
        print("Sticky bits: %u" % self.stickybits)
        return ret
        
    def getSequencerStatus(self):
        seqstat = (c_uint8 * 1)()
        ret = self.read(TI_I2C_RADDR, TI_REG_R_MAIN_STATUS, 1, seqstat, 1)
        if ret != ERROR_OK:
            self.disconnectServer()
            return ret
        self.seqstat = int.from_bytes(seqstat, byteorder='big', signed=False)
        print("Sequencer status: %u" % self.seqstat)
        return ret
        
    def setLedTempLimit(self, limit):
        self.ledTempLimit = int(limit)
        ret = writeLedParam(param = self.ledTempLimit*10, memAddr = LED_LED_TEMP_LIMIT_REGISTER)
        if ret != ERROR_OK:
            self.disconnectServer()
        return ret
        
    def setBoardTempLimit(self, limit):
        self.boardTempLimit = int(limit)
        ret = writeLedParam(param = self.boardTempLimit, memAddr = LED_BOARD_TEMP_LIMIT_REGISTER)
        if ret != ERROR_OK:
            self.disconnectServer()
        return ret
        
    def setOcpLimit(self, limit):
        self.ocpLimit = round(limit/OCP_AMP_PER_UNIT_HW_VER1)
        ret = writeLedParam(param = self.ocpLimit, memAddr = LED_OCPVALUE_REGISTER)
        if ret != ERROR_OK:
            self.disconnectServer()
        return ret
        
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
        