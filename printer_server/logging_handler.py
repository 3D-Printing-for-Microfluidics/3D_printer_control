import logging
import traceback

from printer_server.extensions import db
from printer_server.models import ServerLog


class SQLAlchemyHandler(logging.Handler):
    def __init__(self, app):
        super().__init__()
        self.app = app

    # A very basic logger that commits a LogRecord to the SQL Db
    def emit(self, record):
        trace = None
        exc = record.__dict__["exc_info"]
        if exc:
            trace = traceback.format_exc()

        with self.app.app_context():
            log = ServerLog(
                logger=record.__dict__["name"],
                level=record.__dict__["levelname"],
                trace=trace,
                msg=record.__dict__["msg"],
            )
            log.save()
