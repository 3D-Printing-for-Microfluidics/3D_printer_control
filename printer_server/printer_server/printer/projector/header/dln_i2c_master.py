from ctypes import *
from .dln import *

DLN_PIN_ROLE_I2C_MASTER_SDA             = DLN_PIN_ROLE(0)      #
DLN_PIN_ROLE_I2C_MASTER_SCL             = DLN_PIN_ROLE(0)      #


DLN_MSG_ID_I2C_MASTER_GET_PORT_COUNT    = DLN_BUILD_MSG_ID(0x00, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_ENABLE            = DLN_BUILD_MSG_ID(0x01, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_DISABLE           = DLN_BUILD_MSG_ID(0x02, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_IS_ENABLED        = DLN_BUILD_MSG_ID(0x03, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_SET_FREQUENCY     = DLN_BUILD_MSG_ID(0x04, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_GET_FREQUENCY     = DLN_BUILD_MSG_ID(0x05, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_WRITE             = DLN_BUILD_MSG_ID(0x06, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_READ              = DLN_BUILD_MSG_ID(0x07, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_SCAN_DEVICES      = DLN_BUILD_MSG_ID(0x08, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_PULLUP_ENABLE     = DLN_BUILD_MSG_ID(0x09, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_PULLUP_DISABLE    = DLN_BUILD_MSG_ID(0x0A, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_PULLUP_IS_ENABLED = DLN_BUILD_MSG_ID(0x0B, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_TRANSFER          = DLN_BUILD_MSG_ID(0x0C, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_SET_MAX_REPLY_COUNT= DLN_BUILD_MSG_ID(0x0D, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_GET_MAX_REPLY_COUNT= DLN_BUILD_MSG_ID(0x0E, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_GET_MIN_FREQUENCY = DLN_BUILD_MSG_ID(0x40, DLN_MODULE_I2C_MASTER)      #
DLN_MSG_ID_I2C_MASTER_GET_MAX_FREQUENCY = DLN_BUILD_MSG_ID(0x41, DLN_MODULE_I2C_MASTER)      #


DLN_I2C_MASTER_ENABLED                  = 1      #
DLN_I2C_MASTER_DISABLED                 = 0      #

DLN_I2C_MASTER_MEM_ADDRESS_NONE         = 0      #
DLN_I2C_MASTER_MEM_ADDRESS_1_BYTE       = 1      #
DLN_I2C_MASTER_MEM_ADDRESS_2_BYTES      = 2      #
DLN_I2C_MASTER_MEM_ADDRESS_3_BYTES      = 3      #
DLN_I2C_MASTER_MEM_ADDRESS_4_BYTES      = 4      #

DLN_I2C_MASTER_PULLUP_ENABLED           = 1      #
DLN_I2C_MASTER_PULLUP_DISABLED          = 0      #


class DLN_I2C_MASTER_GET_PORT_COUNT_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
    ]

class DLN_I2C_MASTER_GET_PORT_COUNT_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('count', c_uint8),                  #
    ]


class DLN_I2C_MASTER_ENABLE_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
    ]

class DLN_I2C_MASTER_ENABLE_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('conflict', c_uint16),              #
    ]


class DLN_I2C_MASTER_DISABLE_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
    ]

class DLN_I2C_MASTER_DISABLE_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
    ]


class DLN_I2C_MASTER_IS_ENABLED_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
    ]


class DLN_I2C_MASTER_IS_ENABLED_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('enabled', c_uint8),                #
    ]


class DLN_I2C_MASTER_SET_FREQUENCY_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
        ('frequency', c_uint32),             #
    ]

class DLN_I2C_MASTER_SET_FREQUENCY_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('frequency', c_uint32),             #
    ]


class DLN_I2C_MASTER_GET_FREQUENCY_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
    ]

class DLN_I2C_MASTER_GET_FREQUENCY_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('frequency', c_uint32),             #
    ]


DLN_I2C_MASTER_MAX_TRANSFER_SIZE        = 256      #

class DLN_I2C_MASTER_WRITE_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
        ('slaveDeviceAddress', c_uint8),     #
        ('memoryAddressLength', c_uint8),    #
        ('memoryAddress', c_uint32),         #
        ('bufferLength', c_uint16),          #
        ('buffer', c_uint8 * DLN_I2C_MASTER_MAX_TRANSFER_SIZE),#
    ]

class DLN_I2C_MASTER_WRITE_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
    ]


class DLN_I2C_MASTER_READ_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
        ('slaveDeviceAddress', c_uint8),     #
        ('memoryAddressLength', c_uint8),    #
        ('memoryAddress', c_uint32),         #
        ('bufferLength', c_uint16),          #
    ]

class DLN_I2C_MASTER_READ_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('bufferLength', c_uint16),          #
        ('buffer', c_uint8 * DLN_I2C_MASTER_MAX_TRANSFER_SIZE),#
    ]


class DLN_I2C_MASTER_SCAN_DEVICES_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
    ]

class DLN_I2C_MASTER_SCAN_DEVICES_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('addressCount', c_uint8),           #
        ('addressList', c_uint8 * 128),       #
    ]


class DLN_I2C_MASTER_PULLUP_ENABLE_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
    ]

class DLN_I2C_MASTER_PULLUP_ENABLE_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
    ]


class DLN_I2C_MASTER_PULLUP_DISABLE_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
    ]

class DLN_I2C_MASTER_PULLUP_DISABLE_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
    ]


class DLN_I2C_MASTER_PULLUP_IS_ENABLED_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
    ]

class DLN_I2C_MASTER_PULLUP_IS_ENABLED_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('enabled', c_uint8),                #
    ]


class DLN_I2C_MASTER_TRANSFER_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
        ('slaveDeviceAddress', c_uint8),     #
        ('writeLength', c_uint16),           #
        ('readLength', c_uint16),            #
        ('writeBuffer', c_uint8 * DLN_I2C_MASTER_MAX_TRANSFER_SIZE),#
    ]

class DLN_I2C_MASTER_TRANSFER_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('readLength', c_uint16),            #
        ('readBuffer', c_uint8 * DLN_I2C_MASTER_MAX_TRANSFER_SIZE),#
    ]


class DLN_I2C_MASTER_GET_MIN_FREQUENCY_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
    ]

class DLN_I2C_MASTER_GET_MIN_FREQUENCY_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('frequency', c_uint32),             #
    ]

DLN_I2C_MASTER_GET_MAX_FREQUENCY_CMD    = DLN_I2C_MASTER_GET_MIN_FREQUENCY_CMD      #
DLN_I2C_MASTER_GET_MAX_FREQUENCY_RSP    = DLN_I2C_MASTER_GET_MIN_FREQUENCY_RSP      #


class DLN_I2C_MASTER_SET_MAX_REPLY_COUNT_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
        ('maxReplyCount', c_uint16),         #
    ]

class DLN_I2C_MASTER_SET_MAX_REPLY_COUNT_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
    ]


class DLN_I2C_MASTER_GET_MAX_REPLY_COUNT_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('port', c_uint8),                   #
    ]

class maxReplyCount(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
    ]
