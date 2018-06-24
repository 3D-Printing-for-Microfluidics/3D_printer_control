# -*- coding: utf-8 -*-
"""Create an application instance."""
import os
import logging
import time
from flask.helpers import get_debug_flag

from printer_server.app import create_app
from printer_server.settings import DevConfig, ProdConfig

CONFIG = DevConfig if get_debug_flag() else ProdConfig

logger = logging.getLogger('werkzeug')
logger_filename = os.path.join()
    CONFIG.PROJECT_ROOT, 
    'logs', 
    '{}.log'.format(time.strftime('%Y%m%d'))
)
format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(filename=logger_filename,
                    filemode='a',
                    format=format,
                    level=logging.INFO)

app = create_app(CONFIG)
