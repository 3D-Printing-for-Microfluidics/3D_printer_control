from printer_server.printer_server.printer.projector.i2c.rpi.i2cdriver import LightEngineI2C
from printer_server.printer_server.printer.projector.i2c.rpi.constants import *
l = LightEngineI2C()
l.dmd = l.pi.i2c_open(l.bus, TI_I2C_RADDR>>1)
l.led = l.pi.i2c_open(l.bus, LED_I2C_WADDR>>1)

l.pi.i2c_write_byte_data(l.dmd, TI_REG_W_SEQUENCE, TI_SEQUENCE_OFF)
l.pi.i2c_write_byte_data(l.dmd,TI_REG_W_IT6535,0x0)
mode = l.pi.i2c_read_byte_data(l.dmd, TI_REG_R_DISPLAY_MODE)
l.pi.i2c_write_byte_data(l.dmd,TI_REG_W_DISPLAY_MODE,TI_DISPLAY_MODE_VIDEO_PATTERN)


