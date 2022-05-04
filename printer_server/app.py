"""The app module, containing the app factory function."""
from werkzeug.contrib.fixers import ProxyFix
from flask import Flask, render_template
from printer_server.extensions import db, migrate, socketio
from printer_server.models import PrintRecord, PrintQueue
from printer_server import commands, models
from printer_server.views import home, manual_controls, print_history, server_logs
from printer_server.settings import ProdConfig
from printer_server.hardware_configuration import driver_handles
from printer_server.logging_handler import configure_loggers


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

    with app.app_context():
        cleanup_db()

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
    app.register_blueprint(server_logs.blueprint)


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
    app.driver_handles = driver_handles


def register_logger(app):
    if not app.debug:
        configure_loggers(app)


def cleanup_db():
    PrintQueue().remove_orphaned_entries()
    PrintQueue().remove_orphaned_files()

    PrintRecord().remove_orphaned_entries()
    PrintRecord().remove_orphaned_files()
    PrintRecord().remove_old_jobs()
