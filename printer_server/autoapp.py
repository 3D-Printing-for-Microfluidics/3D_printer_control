# -*- coding: utf-8 -*-
"""Create an application instance."""
import os
import logging
import time
from flask.helpers import get_debug_flag
from flask.logging import default_handler

from printer_server.app import create_app
from printer_server.settings import DevConfig, ProdConfig
from printer_server.logging_handler import SQLAlchemyHandler

CONFIG = DevConfig if get_debug_flag() else ProdConfig

app = create_app(CONFIG)

if not CONFIG.DEBUG:
    sh = SQLAlchemyHandler(app)
    sh.setLevel(logging.WARNING)
    root_logger = logging.getLogger()
    root_logger.addHandler(sh)
    app.logger.removeHandler(default_handler)
    app.logger.addHandler(sh)


if __name__ == '__main__':
    app.run()