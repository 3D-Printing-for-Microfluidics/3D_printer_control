from ctypes import *

DLN_RESTRICTION = c_uint8

DLN_RSTR_NO_RESTICTION                            = DLN_RESTRICTION(0x00)
DLN_RSTR_MUST_BE_DISABLED                         = DLN_RESTRICTION(0x01)
DLN_RSTR_MUST_BE_ENABLED                          = DLN_RESTRICTION(0x02)
DLN_RSTR_MUST_BE_IDLE                             = DLN_RESTRICTION(0x03)

DLN_RSTR_SET_NOT_SUPPORTED                        = DLN_RESTRICTION(0xFE)
DLN_RSTR_COMMAND_NOT_SUPPORTED                    = DLN_RESTRICTION(0xFF)
