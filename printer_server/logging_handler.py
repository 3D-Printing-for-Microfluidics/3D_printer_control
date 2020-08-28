import sys
import traceback
import logging
from logging.handlers import TimedRotatingFileHandler
from functools import wraps
from flask.logging import default_handler


from printer_server.extensions import socketio
from printer_server.models import ServerLog
from printer_server.settings import Config


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


def log_namer(default_filename):
    """Define how log files will be named. Keep extension at end."""
    parts = default_filename.split(".")
    return f"{parts[0]}_{parts[2]}.{parts[1]}"


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


class SocketIOHandler(logging.Handler):
    """A logging handler that emits records with SocketIO."""

    def __init__(self):
        super().__init__()

    def emit(self, record):
        asctime = record.__dict__["asctime"]
        msecs = record.__dict__["msecs"]
        levelname = record.__dict__["levelname"]
        module = record.__dict__["module"]
        message = record.__dict__["message"]
        msg = f"{asctime}.{round(msecs):03} [{levelname:<5.5s}]  {module:<18s}  {message}"
        socketio.emit("update_message_box", msg, namespace="/printing", broadcast=True)


class LoggingNameFilter(logging.Filter):
    """Strip out only the last part of a name to use with a logger."""

    def filter(self, record):
        record.shortname = record.name.rsplit(".", 1)[-1]
        return True


def configure_loggers(app):
    """Configure the loggers that will be shared for the app."""
    host = Config.HOSTNAME
    fmt = "%(asctime)s.%(msecs)03d [%(levelname)-5.5s]  %(shortname)-18s  %(message)s"

    app.logger.removeHandler(default_handler)
    root_logger = logging.getLogger()
    # root_logger.setLevel(logging.NOTSET)  # uncomment to see all mesasges everywhere

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.addFilter(LoggingNameFilter())
    console_handler.setFormatter(logging.Formatter(fmt, "%Y-%m-%d %H:%M:%S"))
    root_logger.addHandler(console_handler)

    log_file_handler = TimedRotatingFileHandler(f"logs/{host}_log.txt", when="midnight")
    log_file_handler.addFilter(LoggingNameFilter())
    log_file_handler.setFormatter(logging.Formatter(fmt, "%Y-%m-%d %H:%M:%S"))
    log_file_handler.namer = log_namer
    root_logger.addHandler(log_file_handler)

    flask_socketIO_handler = SocketIOHandler()
    root_logger.addHandler(flask_socketIO_handler)
