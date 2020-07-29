# -*- coding: utf-8 -*-
"""The app module, containing the app factory function."""
import sys
import logging
from werkzeug.contrib.fixers import ProxyFix
from flask import Flask, render_template
from flask.logging import default_handler
from printer_server.extensions import db, migrate, socketio
from printer_server import commands, models
from printer_server.views import home, manual_controls, print_history, chart
from printer_server.settings import ProdConfig
from printer_server.hardware_configuration import hardware_driver_handles
from printer_server.logging_handler import SQLAlchemyHandler, LoggingNameFilter


def create_app(config_object=ProdConfig):
    """An application factory, as explained here:
    http://flask.pocoo.org/docs/patterns/appfactories/.

    :param config_object: The configuration object to use.
    """
    app = Flask(__name__.split(".")[0])
    app.config.from_object(config_object)
    app.wsgi_app = ProxyFix(app.wsgi_app)
    register_extensions(app)
    register_blueprints(app)
    register_errorhandlers(app)
    register_shellcontext(app)
    register_commands(app)
    register_hardware(app)
    register_logger(app)
    return app


def register_extensions(app):
    """Register Flask extensions."""
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)


def register_blueprints(app):
    """Register Flask blueprints."""
    app.register_blueprint(home.blueprint)
    app.register_blueprint(manual_controls.blueprint)
    app.register_blueprint(print_history.blueprint)
    app.register_blueprint(chart.blueprint)


def register_errorhandlers(app):
    """Register error handlers."""

    def render_error(error):
        """Render error template."""
        # If a HTTPException, pull the `code` attribute; default to 500
        error_code = getattr(error, "code", 500)
        return render_template("{}.html".format(error_code), msg=error), error_code

    for errcode in [404, 500]:
        app.errorhandler(errcode)(render_error)


def register_shellcontext(app):
    """Register shell context objects."""

    def shell_context():
        """Shell context objects."""
        return {"db": db, "User": models.User}

    app.shell_context_processor(shell_context)


def register_commands(app):
    """Register Click commands."""
    app.cli.add_command(commands.test)
    app.cli.add_command(commands.lint)
    app.cli.add_command(commands.clean)
    app.cli.add_command(commands.urls)


def register_hardware(app):
    app.hardware_driver_handles = hardware_driver_handles


def register_logger(app):
    if not app.debug:
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
        fmt = "%(asctime)s.%(msecs)03d [%(levelname)-5.5s]  %(name_last)s  %(message)s"
        console_handler.setFormatter(logging.Formatter(fmt, "%Y-%m-%d %H:%M:%S"))
        console_handler.addFilter(LoggingNameFilter())
        root_logger.addHandler(console_handler)
        app.logger.addHandler(console_handler)
