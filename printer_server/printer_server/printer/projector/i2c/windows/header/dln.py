from ctypes import *
from .dln_results import *
from .dln_restrictions import *

HDLN                               = c_uint16
HDLN_ALL_DEVICES                   = HDLN(0)      #
HDLN_INVALID_HANDLE                = HDLN(0xFFFF)      #

DLN_MAX_MSG_SIZE                   = 288      #

#####################################################
#### Commands group and macros
#####################################################
DLN_MSG_ID                         = c_uint16      #
DLN_MODULE                         = c_uint8      #
DLN_MODULE_GENERIC                 = DLN_MODULE(0x00)      #/< Common commands
DLN_MODULE_GPIO                    = DLN_MODULE(0x01)      #/< Command for GPIO module
DLN_MODULE_SPI_MASTER              = DLN_MODULE(0x02)      #/< Command for SPI module
DLN_MODULE_I2C_MASTER              = DLN_MODULE(0x03)      #/< Command for I2C module
DLN_MODULE_LED                     = DLN_MODULE(0x04)      #/< Command for LED module
DLN_MODULE_BOOT                    = DLN_MODULE(0x05)      #/< Command for BOOT module
DLN_MODULE_ADC                     = DLN_MODULE(0x06)      #/< Command for ADC module
DLN_MODULE_PWM                     = DLN_MODULE(0x07)      #/< Command for PWM module
DLN_MODULE_FREQ                    = DLN_MODULE(0x08)      #/< Command for Freq. counter module
DLN_MODULE_I2S                     = DLN_MODULE(0x09)      #
DLN_MODULE_SDIO                    = DLN_MODULE(0x0A)      #/< Command for SDIO module
DLN_MODULE_SPI_SLAVE               = DLN_MODULE(0x0B)      #
DLN_MODULE_I2C_SLAVE               = DLN_MODULE(0x0C)      #
DLN_MODULE_PLS_CNT                 = DLN_MODULE(0x0D)      #/< Command for pulse counter module
DLN_MODULE_UART                    = DLN_MODULE(0x0E)      #
DLN_MODULE_SPI_SLAVE_SYNC          = DLN_MODULE(0x0F)      #
DLN_MODULE_I2C_EEPROM              = DLN_MODULE(0x10)      #
DLN_MODULE_SPI_EEPROM              = DLN_MODULE(0x11)      #
DLN_MODULE_SPI_FLASH               = DLN_MODULE(0x12)      #
DLN_MODULE_I2C_DATAFLASH           = DLN_MODULE(0x13)      #
DLN_MODULE_ANALYZER                = DLN_MODULE(0x14)      #

DLN_MODULE_COUNT                   = c_uint8(0x15)      #
DLN_MSG_MODULE_POSITION            = 8      #/< bit position of group code
DLN_BUILD_MSG_ID                   = lambda id, module: c_int((id) | (module.value)<<DLN_MSG_MODULE_POSITION )     #
DLN_GET_MSG_MODULE                 = lambda x: c_int(((x.value)>>DLN_MSG_MODULE_POSITION) & 0xFF)      #

DLN_PIN_ROLE                       = c_uint8      #

'''!
\struct DLN_MSG_HEADER
The message header is the first field of each message, sent from a host to a device or vice versa. It is used to identify and route the message correctly.
 '''
class DLN_MSG_HEADER(Structure):
    _pack_ = 1
    _fields_ = [
        ('size', c_uint16),        #/< The size of the message.
        ('msgId', DLN_MSG_ID),     #/< The code defining the message.
        ('echoCounter', c_uint16), #/< Used to establish a one-one link between a command/response pair.
        #/ In case the message is an event, this is a freerunning counter.
        ('handle', HDLN),          #/< A handle to the DLN device.
    ]

'''!
\struct DLN_BASIC_RSP
 '''
class DLN_BASIC_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),#
        ('result', DLN_RESULT),    #
    ]

'''!
\struct DLN_BASIC_CMD
 '''
class DLN_BASIC_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),#
    ]






