from ctypes import *
from .dln import *

DWORD     = c_ulong
HWND      = c_void_p
HANDLE    = c_void_p
UINT      = c_uint


DLN_PIN_ROLE_NOT_IN_USE                 = DLN_PIN_ROLE(0)     #


DLN_MSG_ID_REGISTER_NOTIFICATION        = DLN_BUILD_MSG_ID(0x00, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_UNREGISTER_NOTIFICATION      = DLN_BUILD_MSG_ID(0x01, DLN_MODULE_GENERIC)      #

DLN_MSG_ID_CONNECT                      = DLN_BUILD_MSG_ID(0x10, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_DISCONNECT                   = DLN_BUILD_MSG_ID(0x11, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_DISCONNECT_ALL               = DLN_BUILD_MSG_ID(0x12, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_GET_SRV_UUID                 = DLN_BUILD_MSG_ID(0x13, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_CLEANUP                      = DLN_BUILD_MSG_ID(0x14, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_CONNECTION_LOST_EV           = DLN_BUILD_MSG_ID(0x1F, DLN_MODULE_GENERIC)      #


DLN_MSG_ID_GET_DEVICE_COUNT             = DLN_BUILD_MSG_ID(0x20, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_OPEN_DEVICE                  = DLN_BUILD_MSG_ID(0x21, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_OPEN_STREAM                  = DLN_BUILD_MSG_ID(0x22, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_CLOSE_HANDLE                 = DLN_BUILD_MSG_ID(0x23, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_CLOSE_ALL_HANDLES            = DLN_BUILD_MSG_ID(0x24, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_DEVICE_REMOVED_EV            = DLN_BUILD_MSG_ID(0x2E, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_DEVICE_ADDED_EV              = DLN_BUILD_MSG_ID(0x2F, DLN_MODULE_GENERIC)      #


DLN_MSG_ID_GET_VER                      = DLN_BUILD_MSG_ID(0x30, DLN_MODULE_GENERIC)      #/< Get HW, SW and protocol version
DLN_MSG_ID_GET_DEVICE_SN                = DLN_BUILD_MSG_ID(0x31, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_SET_DEVICE_ID                = DLN_BUILD_MSG_ID(0x32, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_GET_DEVICE_ID                = DLN_BUILD_MSG_ID(0x33, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_GET_HARDWARE_TYPE            = DLN_BUILD_MSG_ID(0x34, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_GET_HARDWARE_VERSION         = DLN_BUILD_MSG_ID(0x35, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_GET_FIRMWARE_VERSION         = DLN_BUILD_MSG_ID(0x36, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_GET_SERVER_VERSION           = DLN_BUILD_MSG_ID(0x37, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_GET_LIBRARY_VERSION          = DLN_BUILD_MSG_ID(0x38, DLN_MODULE_GENERIC)      #

DLN_MSG_ID_GET_PIN_CFG                  = DLN_BUILD_MSG_ID(0x40, DLN_MODULE_GENERIC)      #

DLN_MSG_ID_GET_COMMAND_RESTRICTION      = DLN_BUILD_MSG_ID(0x41, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_DELAY                        = DLN_BUILD_MSG_ID(0x42, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_RESTART                      = DLN_BUILD_MSG_ID(0x43, DLN_MODULE_GENERIC)      #

DLN_MSG_ID_SET_SRV_PARAMS               = DLN_BUILD_MSG_ID(0x44, DLN_MODULE_GENERIC)      #
DLN_MSG_ID_GET_SRV_PARAMS               = DLN_BUILD_MSG_ID(0x45, DLN_MODULE_GENERIC)      #


##############################################
#### Device types
##############################################
DLN_HW_TYPE                             = c_uint32      #
DLN_HW_TYPE_DLN5                        = DLN_HW_TYPE(0x0500)      #
DLN_HW_TYPE_DLN4M                       = DLN_HW_TYPE(0x0401)      #
DLN_HW_TYPE_DLN4S                       = DLN_HW_TYPE(0x0402)      #
DLN_HW_TYPE_DLN3                        = DLN_HW_TYPE(0x0300)      #
DLN_HW_TYPE_DLN2                        = DLN_HW_TYPE(0x0200)      #
DLN_HW_TYPE_DLN1                        = DLN_HW_TYPE(0x0100)      #

#call back(handler of the asynchronous operations)
# PDLN_CALLBACK = CFUNCTYPE(c_void_p, (HDLN, c_void_p,))
DLN_NOTIFICATION_TYPE                   = c_uint16
    
DLN_NOTIFICATION_TYPE_NO_NOTIFICATION   = DLN_NOTIFICATION_TYPE(0x00)      #
DLN_NOTIFICATION_TYPE_CALLBACK          = 0x01      #

DLN_NOTIFICATION_TYPE_EVENT_OBJECT      = 0x02      #
DLN_NOTIFICATION_TYPE_WINDOW_MESSAGE    = 0x03      #
DLN_NOTIFICATION_TYPE_THREAD_MESSAGE    = 0x04      #
DLN_NOTIFICATION_TYPE_LAB_VIEW_EVENT    = 0x05      #


# typedef struct _DLN_NOTIFICATION


##############################################
#### Common commands
##############################################
'''
\struct DLN_REGISTER_NOTIFICATION_CMD
The command registers notification settings
'''
# class DLN_REGISTER_NOTIFICATION_CMD(Structure):
#     _pack_ = 1
#     _fields_ = [
#         ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
#         ('notification', DLN_NOTIFICATION),  #/< Defines the notification settings.
#     ]

'''
\struct DLN_REGISTER_NOTIFICATION_RSP
The response notifies whether the settings were successfully registered.
'''
class DLN_REGISTER_NOTIFICATION_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
    ]

'''
\struct DLN_UNREGISTER_NOTIFICATION_CMD
The command unregisters notification settings.
'''
class DLN_UNREGISTER_NOTIFICATION_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
    ]

'''
\struct DLN_UNREGISTER_NOTIFICATION_RSP
The response notifies whether the settings were successfully unregistered.
'''
class DLN_UNREGISTER_NOTIFICATION_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
    ]

DLN_MAX_HOST_LENGTH                     = 50      #
DLN_DEFAULT_SERVER_PORT                 = c_uint16(9656)      #
'''
\struct DLN_CONNECT_CMD
The command establishes the connection to the DLN server.
'''
class DLN_CONNECT_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        #/  For the header.handle the HDLN_ALL_DEVICES value must be used.
        ('host', c_char * (DLN_MAX_HOST_LENGTH+1)),#/< A server to establish the connection to.
        ('port', c_uint16),                  #/< A port number of the DLN server.
    ]
'''
\struct DLN_CONNECT_RSP
The response notifies if the connection was successfully established.
'''
class DLN_CONNECT_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
    ]


'''
\struct DLN_DISCONNECT_CMD
The closes the connection to the specified DLN server.

'''
class DLN_DISCONNECT_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        #/  For the header.handle the HDLN_ALL_DEVICES value must be used.
        ('host', c_char * (DLN_MAX_HOST_LENGTH+1)),#/< A server to close the connection to.
        ('port', c_uint16),                  #/< A port number of the DLN server.
    ]

'''
\struct DLN_DISCONNECT_RSP
The response notifies if the connection was successfully closed.
'''
class DLN_DISCONNECT_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
    ]

'''
\struct DLN_DISCONNECT_ALL_CMD
The command closes connections to all servers at once.
'''
class DLN_DISCONNECT_ALL_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        #/  For the header.handle the HDLN_ALL_DEVICES value must be used.
    ]


'''
\struct DLN_DISCONNECT_ALL_RSP
The response notifies if all the connections were successfully closed.
'''
class DLN_DISCONNECT_ALL_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        #/  For the header.handle the HDLN_ALL_DEVICES value must be used.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
    ]


class DLN_GET_SRV_UUID_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
    ]

class DLN_GET_SRV_UUID_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('uuid', c_uint8 * 16),               #
    ]


class DLN_CLEANUP_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
    ]

class DLN_CLEANUP_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
    ]

'''
\struct DLN_CONNECTION_LOST_EV
'''
class DLN_CONNECTION_LOST_EV(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('host', c_char * (DLN_MAX_HOST_LENGTH+1)),#
        ('port', c_uint16),                  #
    ]


DLN_DEVICE_FILTER_NUMBER                = (1<<0)      #
DLN_DEVICE_FILTER_HW_TYPE               = (1<<1)      #
DLN_DEVICE_FILTER_SN                    = (1<<2)      #
DLN_DEVICE_FILTER_ID                    = (1<<3)      #

'''
\struct DLN_GET_DEVICE_COUNT_CMD
The command retrieves the total number of DLN-devices available.
'''
class DLN_GET_DEVICE_COUNT_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        #/  For the header.handle the HDLN_ALL_DEVICES value must be used.
        ('filter', c_uint16),                #
        ('hardwareType', c_uint32),          #/< A type of the device.
        ('sn', c_uint32),                    #/< A serial number of the device.
        ('id', c_uint32),                    #/< An ID number of the device.
    ]

'''
\struct DLN_GET_DEVICE_COUNT_RSP
The response notifies if the device was successfully opened.
'''
class DLN_GET_DEVICE_COUNT_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
        ('deviceCount', c_uint32),           #/< The number of connected devices.
    ]

'''
\struct DLN_OPEN_DEVICE_CMD
The command opens the specified device.
'''
class DLN_OPEN_DEVICE_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        #/  For the header.handle the HDLN_ALL_DEVICES value must be used.
        ('filter', c_uint16),                #/< Defines which parameters are used to choose the device.
        ('number', c_uint32),                #/< A number of the device to open (bit 0 of the filter must be set to use the number field).
        ('hardwareType', DLN_HW_TYPE),       #/< A type of the device.
        ('sn', c_uint32),                    #/< A type of the device.
        ('id', c_uint32),                    #/< An ID number of the device.
    ]

'''
\struct DLN_OPEN_DEVICE_RSP
The response notifies if the device was successfully opened.
'''

class DLN_OPEN_DEVICE_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
        ('deviceHandle', HDLN),              #/< A handle to the DLN device.
    ]

'''
\struct DLN_OPEN_STREAM_CMD
'''
class DLN_OPEN_STREAM_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
    ]

'''
\struct DLN_OPEN_STREAM_RSP
'''
class DLN_OPEN_STREAM_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('streamHandle', HDLN),              #
    ]

'''
\struct DLN_CLOSE_HANDLE_CMD
The command closes the handle to the opened DLN device (stream).
'''
class DLN_CLOSE_HANDLE_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
    ]

'''
\struct DLN_CLOSE_HANDLE_RSP
The response notifies if the connection was successfully closed.
'''
class DLN_CLOSE_HANDLE_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
    ]

'''
\struct DLN_CLOSE_ALL_HANDLES_CMD
The command closes all handles to opened DLN devices (stream).
'''
class DLN_CLOSE_ALL_HANDLES_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        #/  For the header.handle the HDLN_ALL_DEVICES value must be used.
    ]

'''
\struct DLN_CLOSE_ALL_HANDLES_RSP
The response notifies if all connections were successfully closed.
'''
class DLN_CLOSE_ALL_HANDLES_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
    ]

'''
\struct DLN_DEVICE_REMOVED_EV
The event notifies about a device having being disconnected from a server.
'''
class DLN_DEVICE_REMOVED_EV(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
    ]

'''
\struct DLN_DEVICE_ADDED_EV
The event notifies about a device being connected to a server.
'''
class DLN_DEVICE_ADDED_EV(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('hardwareType', DLN_HW_TYPE),       #/< The type of the device.
        ('id', c_uint32),                    #/< The device ID number.
        ('sn', c_uint32),                    #/< The device serial number.
    ]



'''
\struct DLN_VERSION
The structure is used to store the DLN device and software version data.
'''
class DLN_VERSION(Structure):
    _pack_ = 1
    _fields_ = [
        ('hardwareType', DLN_HW_TYPE),       #/< A type of the device.
        ('hardwareVersion', c_uint32),       #/< A version of the hardware, used in he device.
        ('firmwareVersion', c_uint32),       #/< A version of the firmware, installed in the device.
        ('serverVersion', c_uint32),         #/< A version of the DLN server.
        ('libraryVersion', c_uint32),        #/< A version of the DLN-library.
    ]

'''
\struct DLN_GET_VER_CMD
The command retrieves the DLN device and software version data.
'''
class DLN_GET_VER_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
    ]
'''
\struct DLN_GET_VER_RSP
The response contains the retrieved information.
'''
class DLN_GET_VER_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
        ('version', DLN_VERSION),            #/< The DLN_VERSION structure, containing the version information.
    ]

'''
\struct DLN_GET_DEVICE_SN_CMD
The command retrieves a device serial number.
'''
class DLN_GET_DEVICE_SN_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
    ]

'''
\struct DLN_GET_DEVICE_SN_RSP
The response contains a device serial number.
'''
class DLN_GET_DEVICE_SN_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
        ('sn', c_uint32),                    #/< A device serial number.
    ]

'''
\struct DLN_SET_DEVICE_ID_CMD
The command sets a new ID to the DLN device.
'''
class DLN_SET_DEVICE_ID_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('id', c_uint32),                    #/< A new device ID to be set.
    ]

'''
\struct DLN_SET_DEVICE_ID_RSP
The response notifies if the ID was successfully set.
'''
class DLN_SET_DEVICE_ID_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
    ]

'''
\struct DLN_GET_DEVICE_ID_CMD
The command retrieves the device ID number.
'''
class DLN_GET_DEVICE_ID_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
    ]

'''
\struct DLN_GET_DEVICE_ID_RSP
The response contains the retrieved device ID number.
'''
class DLN_GET_DEVICE_ID_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
        ('id', c_uint32),                    #/< A device ID number.
    ]

'''
\struct DLN_GET_HARDWARE_TYPE_CMD
The command retrieves the device hardware type (e.g DLN_HW_TYPE_DLN4M, DLN_HW_TYPE_DLN2)
'''
class DLN_GET_HARDWARE_TYPE_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
    ]

'''
\struct DLN_GET_HARDWARE_TYPE_RSP
The response contains the retrieved device hardware type.
'''
class DLN_GET_HARDWARE_TYPE_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('type', DLN_HW_TYPE),               #
    ]


class DLN_GET_HARDWARE_VERSION_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
    ]

class DLN_GET_HARDWARE_VERSION_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('version', c_uint32),               #
    ]

class DLN_GET_FIRMWARE_VERSION_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
    ]

class DLN_GET_FIRMWARE_VERSION_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('version', c_uint32),               #
    ]

class DLN_GET_SERVER_VERSION_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
    ]

class DLN_GET_SERVER_VERSION_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('version', c_uint32),               #
    ]

class DLN_GET_LIBRARY_VERSION_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
    ]

class DLN_GET_LIBRARY_VERSION_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('version', c_uint32),               #
    ]


'''
\struct DLN_PIN_CFG
The structure is used to store the configuration of a single DLN device pin.
'''
class DLN_PIN_CFG(Structure):
    _pack_ = 1
    _fields_ = [
        ('module', DLN_MODULE),              #/< A module, to which the pin is connected.
        ('role', DLN_PIN_ROLE),              #/< A role performed by the pin.
    ]

DLN_DMA_ROLE                            = c_uint8     #
DLN_DMA_ROLE_NOT_IN_USE                 = DLN_DMA_ROLE(0)      #
DLN_DMA_ROLE_TX                         = DLN_DMA_ROLE(1)      #
DLN_DMA_ROLE_RX                         = DLN_DMA_ROLE(2)      #
'''
\struct DLN_GET_PIN_CFG_CMD
'''
class DLN_DMA_CFG(Structure):
    _pack_ = 1
    _fields_ = [
        ('module', DLN_MODULE),              #
        ('role', DLN_DMA_ROLE),              #
    ]

'''
\struct DLN_GET_PIN_CFG_CMD
The command retrieves current configuration of the DLN device pin.
'''
class DLN_GET_PIN_CFG_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('pin', c_uint16),                   #/< A pin to get the configuration from.
    ]

'''
\struct DLN_GET_PIN_CFG_RSP
The  response contains current configuration of the specified DLN device pin.
'''
class DLN_GET_PIN_CFG_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #/< Defines the DLN message header.
        ('result', DLN_RESULT),              #/< Contains the result of the command execution.
        ('cfg', DLN_PIN_CFG),                #/< The current configuration of the pin.
    ]


class DLN_GET_COMMAND_RESTRICTION_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('msgId', DLN_MSG_ID),               #
        ('entity', c_uint16),                #
    ]

class DLN_GET_COMMAND_RESTRICTION_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
        ('restriction', DLN_RESTRICTION),    #
    ]


class DLN_DELAY_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('delay', c_uint32),                 #
    ]

class DLN_DELAY_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
    ]


class DLN_RESTART_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
    ]

class DLN_RESTART_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
    ]


class DLN_SRV_PARAMS(Structure):
    _pack_ = 1
    _fields_ = [
        ('uuid', c_uint8 * 16),               #
        ('deviceHandle', c_uint16),          #
        ('macAddress', c_uint8 * 6),          #
        ('ipAddress', c_uint8 * 4),           #
        ('subnetMask', c_uint8 * 4),          #
        ('gatewayIp', c_uint8 * 4),           #
        ('port', c_uint16),                  #
    ]

class DLN_SET_SRV_PARAMS_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('params', DLN_SRV_PARAMS),          #
    ]

class DLN_SET_SRV_PARAMS_RSP(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
    ]

class DLN_GET_SRV_PARAMS_CMD(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
    ]

class params(Structure):
    _pack_ = 1
    _fields_ = [
        ('header', DLN_MSG_HEADER),          #
        ('result', DLN_RESULT),              #
    ]
