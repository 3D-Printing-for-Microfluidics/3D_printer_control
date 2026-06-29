"""The app module, containing the app factory function."""
import os
import smtplib
import logging
from email.message import EmailMessage
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, render_template, g
from printer_server.extensions import db, migrate, socketio
from printer_server.models import PrintRecord, PrintQueue, Session, Calibration
from printer_server import commands, models
from printer_server.views import home, calibration, manual_controls, print_history, server_logs, users, calibration_history
from printer_server.settings import ProdConfig, DevConfig
from printer_server.hardware_configuration.hardware_configuration import driver_handles
from printer_server.logging_handler import configure_loggers
from printer_server.threading_wrapper import Thread
from flask.helpers import get_debug_flag

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

    @app.before_request
    def build_global_forms():
        # get session info
        session = Session.get_active_session()
        if session:
            g.active_session = {
                "id": session.id,
                "user": session.user.full_name,
                "start_time": session.start_time
            }
        else:
            g.active_session = None

    # add globals
    @app.context_processor
    def inject_globals():
        return {
            "active_session": g.active_session
        }

    @app.template_filter("long_duration")
    def long_duration(td):
        if td is None:
            return ""

        total_seconds = int(td.total_seconds())

        # if less than a minute, show seconds only
        if total_seconds < 60:
            return f"{total_seconds} sec"

        # else if less than a hour, show minutes only
        elif total_seconds < 3600:
            total_minutes = (total_seconds + 30) // 60  # round
            return f"{total_minutes} min"

        # else if less than a day, show hours only
        elif total_seconds < 86400:
            total_hours = (total_seconds + 1800) // 3600  # round
            return f"{total_hours} hr"

        # else show days only
        else:
            total_days = (total_seconds + 43200) // 86400  # round
            return f"{total_days} day{'s' if total_days > 1 else ''}"

    @app.template_filter("duration")
    def duration(td):
        if td is None:
            return ""

        total_seconds = int(td.total_seconds())

        # if more than a day: round to days, hide hours/minutes/seconds
        if total_seconds >= 86400:
            total_days = (total_seconds + 43200) // 86400  # round
            return f"{total_days} day{'s' if total_days > 1 else ''}"

        # 1 hour or more: round to nearest minute, hide seconds
        if total_seconds >= 3600:
            total_minutes = (total_seconds + 30) // 60  # round
            hours, minutes = divmod(total_minutes, 60)

            parts = []
            if hours:
                parts.append(f"{hours} hr")
            if minutes:
                parts.append(f"{minutes} min")

            return " ".join(parts)

        # under 1 hour: show seconds
        hours, rem = divmod(total_seconds, 3600)
        minutes, seconds = divmod(rem, 60)

        parts = []
        if minutes:
            parts.append(f"{minutes} min")
        if seconds or not parts:
            parts.append(f"{seconds} sec")

        return " ".join(parts)

    try:
        calibration.extract_calibration_print_archives()
    except Exception as ex:
        logging.getLogger(__name__).warning(
            "Failed to extract calibration print archives on startup: %s", ex
        )

    # try:
    
        # with app.app_context():
        #     Calibration.init_Calibration_from_old_text_logs()
    # except Exception as ex:
    #     logging.getLogger(__name__).warning(
    #         "Failed to initialize calibration from old text logs on startup: %s", ex
    #     )

    try:
        with app.app_context():
            cleanup_db()
    except:
        print(f"Error cleaning DB. Does it exist?")

    return app


def register_extensions(app):
    """Register Flask extensions."""
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)


def register_blueprints(app):
    """Register Flask blueprints."""
    app.register_blueprint(home.blueprint)
    app.register_blueprint(calibration.blueprint)
    app.register_blueprint(manual_controls.blueprint)
    app.register_blueprint(print_history.blueprint)
    app.register_blueprint(server_logs.blueprint)
    app.register_blueprint(users.blueprint)
    app.register_blueprint(calibration_history.blueprint)


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
    PrintQueue.remove_orphaned_entries()
    PrintQueue.remove_orphaned_files()

    PrintRecord.remove_orphaned_entries()
    PrintRecord.remove_orphaned_files()
    PrintRecord.remove_old_jobs()
    PrintRecord.remove_old_logs()

CONFIG = DevConfig if get_debug_flag() else ProdConfig
app = create_app(CONFIG)

def send_email(recipient, subject, body_html):
    thread = Thread(log=logging.getLogger(__name__), target=_send_email, args=(recipient, subject, body_html))
    thread.start()

def _send_email(recipient, subject, body_html):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = CONFIG.SMTP_USERNAME
    msg["To"] = recipient

    msg.set_content("This email requires an HTML-capable client.")

    msg.add_alternative(body_html, subtype="html")

    try:
        with smtplib.SMTP(CONFIG.SMTP_SERVER, CONFIG.SMTP_PORT) as server:
            server.starttls()
            server.login(CONFIG.SMTP_USERNAME, CONFIG.SMTP_PASSWORD)
            server.send_message(msg)

        logging.getLogger(__name__).info("Email sent successfully!")

    except Exception as e:
        logging.getLogger(__name__).info(f"An error occurred: {e}")
