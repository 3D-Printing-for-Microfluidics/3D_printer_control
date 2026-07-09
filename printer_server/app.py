"""The app module, containing the app factory function."""
import os
import smtplib
import logging
import time
from datetime import datetime, timedelta
from threading import Lock
from email.message import EmailMessage
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, render_template, g
from flask_login import current_user
from printer_server.extensions import db, migrate, socketio, login
from printer_server.models import PrintRecord, PrintQueue, Session, Calibration, User
from printer_server import commands, models
from printer_server.views import home, calibration, manual_controls, print_history, server_logs, users, calibration_history
from printer_server.views.users import require_permissions
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

    # first time database setup (fill tables with default data)
    @app.cli.command("seed-db")
    def seed_db_command():
        if not User.query.filter_by(username="admin").first():
            admin = User(
                first_name="admin",
                last_name="",
                email="admin@email.test",
                username="admin",
                password=config_object.ADMIN_PWD,
            )
            admin.admin_permissions = True
            admin.save()

            default = User(
                first_name="default",
                last_name="",
                email="default@email.test",
                username="default",
                password=config_object.ADMIN_PWD,
            )
            default.print_permissions = True
            default.save()

            print("User table seeded with default users.")

        if not Calibration.query.first():
            # try:
            #     with app.app_context():
            Calibration.init_Calibration_from_old_text_logs()
            print("Moved calibration data from old text logs.")
            # except Exception as ex:
            #     logging.getLogger(__name__).warning(
            #         "Failed to initialize calibration from old text logs on startup: %s", ex
            #     )

    # monitor activity for session timeout
    @app.before_request
    def record_request():
        update_activity()

    # load session active for all templates
    @app.before_request
    def build_global_forms():
        # get session info
        session = Session.get_active_session()
        g.active_session = None
        if session:
            g.active_session = {
                "id": session.id,
                "user": session.user.full_name,
                "start_time": session.start_time
            }
        
        g.current_user = None
        g.is_admin = False
        if current_user.is_authenticated:
            g.current_user = current_user.full_name if current_user.full_name else current_user.username
            g.is_admin = current_user.admin_permissions
            

    # add globals
    @app.context_processor
    def inject_globals():
        return {
            "active_session": g.active_session,
            "current_user": g.current_user,
            "is_admin": g.is_admin,
            "server_time": datetime.now(),
            "session_expiration_minutes": app.config["SESSION_EXPIRATION_MINUTES"],
            "open_access": app.config["OPEN_ACCESS"],
            "open_registration": app.config["OPEN_REGISTRATION"],
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

    try:
        with app.app_context():
            cleanup_db()
    except:
        print(f"Error cleaning DB. Does it exist?")

    return app

########### monitor activity for session timeout ###########

session_active_on_boot = None
last_activity = time.monotonic()
activity_lock = Lock()

def update_activity():
    global last_activity
    with activity_lock:
        last_activity = time.monotonic()

# Override socketio.on_event and socketio.emit to update last_activity on any event or emit
def install_on_event_hook(socketio):
    original_on_event = socketio.on_event
    def on_event(event, handler, namespace=None):
        def wrapped(*args, **kwargs):
            update_activity()
            return handler(*args, **kwargs)
        return original_on_event(event, wrapped, namespace=namespace)
    socketio.on_event = on_event

def install_emit_hook(socketio):
    original_socketio_emit = socketio.emit
    original_server_emit = socketio.server.emit

    def emit(event, *args, **kwargs):
        update_activity()
        return original_socketio_emit(event, *args, **kwargs)

    def server_emit(event, *args, **kwargs):
        update_activity()
        return original_server_emit(event, *args, **kwargs)

    socketio.emit = emit
    socketio.server.emit = server_emit

def idle_monitor(session_timeout_minutes=60, check_interval_seconds=60):
    while True:
        socketio.sleep(check_interval_seconds)

        with activity_lock:
            idle = time.monotonic() - last_activity

        # session timeout
        if idle > timedelta(minutes=session_timeout_minutes):
            with app.app_context():
                session = Session.get_active_session()
                if session:
                    logging.getLogger(__name__).info(
                        "Session %s has been idle for %s, ending session",
                        session.id,
                        idle,
                    )
                    from printer_server.views.users import end_session_timeout
                    from printer_server.forms import EndSessionForm
                    end_session_timeout(session.id)
                
            update_activity()

#############################################################


def register_extensions(app):
    """Register Flask extensions."""
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)
    login.init_app(app)
    login.login_view = "users.do_login"

    install_on_event_hook(socketio)
    install_emit_hook(socketio)
    socketio.start_background_task(
        idle_monitor, 
        session_timeout_minutes=app.config["SESSION_EXPIRATION_MINUTES"],
        check_interval_seconds=60
    )


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

    @require_permissions(require_session=False)
    def render_error(error):
        """Render error template."""
        # If a HTTPException, pull the `code` attribute; default to 500
        error_code = getattr(error, "code", 500)
        return render_template("{}.html".format(error_code), hostname=app.config["HOSTNAME"], msg=error), error_code

    for errcode in [401, 403, 404, 500]:
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
