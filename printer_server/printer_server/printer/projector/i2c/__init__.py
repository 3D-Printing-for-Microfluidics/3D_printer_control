# -*- coding: utf-8 -*-
"""The i2c module"""

# import platform

# if platform.platform().startswith('Windows'):
#     from .windows.i2cdriver import LightEngineI2C
# elif platform.platform().startswith('Linux'):
#     from .rpi.i2cdriver import LightEngineI2C

from .i2cdummy import LightEngineI2C