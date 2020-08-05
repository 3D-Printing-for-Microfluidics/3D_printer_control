import sys
import logging
import traceback
from functools import wraps
from flask.logging import default_handler

from printer_server.extensions import db
from printer_server.models import ServerLog


def dummy_log(f):
    """Decorate function f with a printout of all parameters with their
    values, and f's return value. Used for debugging and dummy hardware
    modules.
    """
    logger = logging.getLogger(f.__qualname__.split(".")[0])
    logger.setLevel(logging.DEBUG)

    @wraps(f)
    def wrapper(*args, **kwargs):
        logger.debug(
            "%s %s",
            f.__qualname__,
            {
                **dict(
                    (k, v) for k, v in zip(f.__code__.co_varnames, args) if k != "self"
                ),
                **kwargs,
            },
        )
        result = f(*args, **kwargs)
        # logger.debug("%s %s %s", f.__qualname__, "return:", result)
        return result

    return wrapper


class SQLAlchemyHandler(logging.Handler):
    """A logging handler that can create logs in the database."""

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
    """Strip out only the last part of a name to use with a logger."""

    def filter(self, record):
        record.name_last = record.name.rsplit(".", 1)[-1]
        return True


def configure_loggers(app):
    """Configure the loggers that will be shared for the app.

    The first logger sends errors to the database. The second one
    formats all logged messages and prints them to the sys.stdout.
    """

    app.logger.removeHandler(default_handler)
    root_logger = logging.getLogger()
    # root_logger.setLevel(logging.NOTSET) # uncomment to see all mesasges everywhere

    # logger that puts records in database
    sh = SQLAlchemyHandler(app)
    sh.setLevel(logging.WARNING)
    root_logger.addHandler(sh)
    app.logger.addHandler(sh)

    # logger to print to console
    console_handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s.%(msecs)03d [%(levelname)-5.5s]  %(name_last)-18s  %(message)s"
    console_handler.setFormatter(logging.Formatter(fmt, "%Y-%m-%d %H:%M:%S"))
    console_handler.addFilter(LoggingNameFilter())
    root_logger.addHandler(console_handler)
    app.logger.addHandler(console_handler)
