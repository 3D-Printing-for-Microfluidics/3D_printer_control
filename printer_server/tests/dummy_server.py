# -*- coding: utf-8 -*-
"""Run a dummy server on PC/Mac without 3D printer hardware."""
import os
import sys

TEST_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(TEST_DIR, '..'))

import types

#########################################
# inject dummy modules for testing

# dummy Solus module
module_name = 'printer_server.printer.solus'
dummy_module = types.ModuleType(module_name)
sys.modules[module_name] = dummy_module
_code = open(os.path.join(TEST_DIR, 'dummy_files', 'dummy_solus.py'), 'rb').read()
exec(_code, dummy_module.__dict__)

# dummy projector module 
module_name = 'printer_server.printer.projector.i2c'
dummy_module = types.ModuleType(module_name)
sys.modules[module_name] = dummy_module
_code = open(os.path.join(TEST_DIR, 'dummy_files', 'dummy_i2c.py'), 'rb').read()
exec(_code, dummy_module.__dict__)

# # dummy calibration control module 
module_name = 'printer_server.printer.calibrationControl'
dummy_module = types.ModuleType(module_name)
sys.modules[module_name] = dummy_module
_code = open(os.path.join(TEST_DIR, 'dummy_files', 'dummy_calibrationControl.py'), 'rb').read()
exec(_code, dummy_module.__dict__)

# dummy hardware module 
module_name = 'printer_server.hardware'
dummy_module = types.ModuleType(module_name)    
sys.modules[module_name] = dummy_module
_code = open(os.path.join(TEST_DIR, 'dummy_files', 'dummy_hardware.py'), 'rb').read()
exec(_code, dummy_module.__dict__)
#########################################


import time
from flask.helpers import get_debug_flag

from printer_server.app import create_app
from printer_server.settings import DevConfig, ProdConfig

CONFIG = DevConfig if get_debug_flag() else ProdConfig

app = create_app(CONFIG)


if __name__ == '__main__':
    # app.run(host='127.0.0.1', port=5000)
    app.run(host='0.0.0.0', port=5000)
