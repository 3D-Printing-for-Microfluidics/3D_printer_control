import logging
import traceback
from functools import wraps

from printer_server.extensions import db
from printer_server.models import ServerLog


def dummy_log(f):
    """Decorate function f with a printout of all parameters with their
    values, and f's return value. Used for debugging and dummy hardware
    modules.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        print(f.__qualname__, {**dict(zip(f.__code__.co_varnames, args)), **kwargs})
        result = f(*args, **kwargs)
        print(f.__qualname__, "return:", result)
        return result

    return wrapper


class SQLAlchemyHandler(logging.Handler):
    def __init__(self, app):
        super().__init__()
        self.app = app

    # A very basic logger that commits a log to the SQL Db
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


class LoggingNameFilter(logging.Filter):
    def filter(self, record):
        record.name_last = record.name.rsplit(".", 1)[-1]
        return True
