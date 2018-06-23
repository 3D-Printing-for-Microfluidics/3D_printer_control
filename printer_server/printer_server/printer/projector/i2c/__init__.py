"""The i2c module"""

# import platform

# if platform.platform().startswith('windows'):
#     from .windows.i2cdriver import LightEngineI2C
# elif platform.platform().startswith('linux'):
#     from .rpi.i2cdriver import LightEngineI2C

from .i2cdummy import LightEngineI2C