import os
import shutil
import logging
from functools import wraps
from flask_socketio import emit, disconnect
from flask_login import login_user, logout_user, current_user, login_required
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, jsonify, send_file, redirect, url_for, abort


from printer_server.settings import Config
from printer_server.extensions import socketio, db, login
from printer_server.views.table import *
import printer_server.views.home as home
from printer_server.forms import LoginForm, StartSessionForm, RegisterForm, EndSessionForm, EndPrintForm, ResetCodeForm, ResetPasswordForm
from printer_server.models import PrintRecord, PrintQueue, Session, User, Calibration
from printer_server.hardware_configuration.hardware_configuration import config_dict
from printer_server.print_file_validator import validate_schema, validate_printer_compatibility

blueprint = Blueprint(
    "users", __name__, url_prefix="/", static_folder="../static"
)
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def get_auth_context():
    open_access = Config.OPEN_ACCESS
    if current_user.is_authenticated:
        return {
            "authenticated": True,
            "user": current_user,
            "is_in_session": Session.get_active_session() is not None,
            "permissions": {
                "print": current_user.print_permissions,
                "calibration": current_user.calibration_permissions,
                "advanced": current_user.advanced_permissions,
                "admin": current_user.admin_permissions,
            },
        }
    if not open_access:
        return {
            "authenticated": False,
            "user": None,
            "is_in_session": False,
            "permissions": {
                "print": False,
                "calibration": False,
                "advanced": False,
                "admin": False,
            },
        }
    session_user = Session.get_session_user()
    if session_user:
        return {
            "authenticated": True,
            "user": session_user,
            "is_in_session": True,
            "permissions": {
                "print": session_user.print_permissions,
                "calibration": session_user.calibration_permissions,
                "advanced": session_user.advanced_permissions,
                "admin": session_user.admin_permissions,
            },
        }
    return {
        "authenticated": True,
        "user": None,
        "is_in_session": False,
        "permissions": {
            "print": False,
            "calibration": False,
            "advanced": False,
            "admin": False,
        },
    }  

def require_permissions(permission=None, require_session=False):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ctx = get_auth_context()
            if not ctx.get("authenticated", False):
                if Config.OPEN_ACCESS:
                    abort(401)
                return redirect(url_for("users.do_login"))
            if require_session and not ctx.get("is_in_session", False):
                abort(401)
            if permission is not None and not ctx.get("permissions", {}).get(permission, False):
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def socket_require_permissions(permission=None, require_session=False):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ctx = get_auth_context()
            if not ctx.get("authenticated", False):
                disconnect()
                return
            if require_session and not ctx.get("is_in_session", False):
                disconnect()
                return
            if permission is not None and not ctx.get("permissions", {}).get(permission, False):
                disconnect()
                return
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@blueprint.route("/login", methods=["GET", "POST"])
def do_login():
    if current_user.is_authenticated:
        return redirect(url_for("home.index"))
    else:
        next_page = request.args.get("next")
        form = LoginForm()
        return render_template("login.html", login_form=form, form=form, hostname=Config.HOSTNAME, next=next_page)

@blueprint.route("/users/login_modal", methods=["GET"])
def login_modal():
    next_page = request.args.get("next") 
    form = LoginForm()
    return render_template("partials/login_modal.html", login_form=form, hostname=Config.HOSTNAME, next=next_page)

@blueprint.route("/users/login_modal", methods=["POST"])
def login_modal_post():
    next_page = request.args.get("next") 
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            home.send_bootstrap_alert("Logged in successfully.", level="success")
            log.info("%s logged in", user.full_name)
            return jsonify({"success": True, "redirect": request.args.get("next") or url_for("home.index")})
        else:
            log.warning("Failed login attempt for username: %s", form.username.data)
            return jsonify({"success": False, "errors": {"username": ["Invalid username or password"]}})
    return jsonify({"success": False, "errors": form.errors})

@blueprint.route("/logout")
@login_required
def do_logout():
    logout_user()
    home.send_bootstrap_alert("You have been logged out.", level="success")
    return redirect(url_for("users.do_login"))

def generate_user_table_column_definition():
    ctx = get_auth_context()
    user = ctx.get("user", None)
    user_id = user.id if user else None
    is_admin = user.admin_permissions if user else False

    columns = [
        Column(key="col-username", name="Username", value=lambda r: r.username, filterable="Yes", visible=True, db_col=User.username, db_filter=generate_string_lambda(User.username)),
        Column(key="col-email", name="Email", value=lambda r: r.email, visible=True, db_col=User.email, db_filter=generate_string_lambda(User.email)),
        Column(key="col-created-at", name="Created At", value=lambda r: r.created_at, type="datetime", db_col=User.created_at, db_filter=generate_datetime_lambda(User.created_at)),
        Column(key="col-first-name", name="First Name", value=lambda r: r.first_name, db_col=User.first_name, db_filter=generate_string_lambda(User.first_name)),
        Column(key="col-last-name", name="Last Name", value=lambda r: r.last_name, db_col=User.last_name, db_filter=generate_string_lambda(User.last_name)),
        Column(key="col-full-name", name="Full Name", value=lambda r: r.full_name, filterable="Yes", visible=True, db_col=User.full_name, db_filter=generate_string_lambda(User.full_name)),
        Column(key="col-print-permissions", name="Print Permissions", value=lambda r: r.print_permissions, type="checkbox", href_enabled=is_admin, button_class="permission-btn", visible=True, db_col=User.print_permissions, db_filter=generate_boolean_lambda(User.print_permissions), vertical_header=True),
        Column(key="col-calibration-permissions", name="Calibration Permissions", value=lambda r: r.calibration_permissions, type="checkbox", href_enabled=is_admin, button_class="permission-btn", visible=True, db_col=User.calibration_permissions, db_filter=generate_boolean_lambda(User.calibration_permissions), vertical_header=True),
        Column(key="col-advanced-permissions", name="Advanced Permissions", value=lambda r: r.advanced_permissions, type="checkbox", href_enabled=is_admin, button_class="permission-btn", visible=True, db_col=User.advanced_permissions, db_filter=generate_boolean_lambda(User.advanced_permissions), vertical_header=True),
        Column(key="col-admin-permissions", name="Admin Permissions", value=lambda r: r.admin_permissions, type="checkbox", href_enabled=lambda r: is_admin and r.username not in ["admin", "default"], button_class="permission-btn", visible=True, db_col=User.admin_permissions, db_filter=generate_boolean_lambda(User.admin_permissions), vertical_header=True),
        Column(key="col-reset", name="Edit User", type="button", href_enabled=lambda r: (r.id == user_id or is_admin) and r.username not in ["admin", "default"], button_style="btn-outline-warning", button_name="Edit", button_class="reset-btn", sortable=False, filterable="No", visible=True),
        Column(key="col-delete", name="Delete User", type="button", href_enabled=lambda r: (r.id == user_id or is_admin) and r.username not in ["admin", "default"], button_style="btn-outline-danger", button_name="Delete", button_class="delete-btn", sortable=False, filterable="No", visible=True)
    ]

    def get_sort_col(column_key):
        map = {}
        for col in columns:
            if col.db_col is not None:
                map[col.key] = col.db_col
        return map.get(column_key, User.created_at)
    
    def get_filter_lambda(column_key):
        map = {}
        for col in columns:
            if col.db_filter is not None:
                map[col.key] = col.db_filter
        return map.get(column_key, lambda x: None)

    return {
        "columns": columns,
        "sort_columns": get_sort_col,
        "filter_lambdas": get_filter_lambda,
    }


@blueprint.route("/users")
@require_permissions(require_session=False)
def index():
    return render_template(
        "users.html",
        hostname=Config.HOSTNAME,
    )


@blueprint.route("/users/user_table")
@require_permissions(require_session=False)
def print_table():
    table = generate_table(
        name = "Users",
        table_key = "user-table", 
        route = "/users/user_table",
        query = User.query, 
        table_definition = generate_user_table_column_definition(),  
        has_filters = True,
        subtables = None,
        paginate = 20, 
        args = request.args
    )
    
    return render_template(
        "partials/table.html",
        table=table
    )


@blueprint.route("/users/session_summary")
@require_permissions(require_session=False)
def session_summary():
    session = Session.get_active_session()
    if not session:
        msg = "Cannot display session summary: No active session"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"session": [msg]}})

    number_of_sessions = 4

    time_since_film_change = Session.query.filter(Session.film_changed == True, Session.start_time <= session.start_time).order_by(Session.start_time.desc()).first()
    time_since_calibration = Calibration.query.filter(Calibration.calibration_date <= session.start_time).order_by(Calibration.calibration_date.desc()).first()
    last_sessions = Session.query.filter(Session.start_time <= session.start_time).order_by(Session.start_time.desc()).limit(number_of_sessions).all()
    total_prints = sum(len(s.print_records) for s in last_sessions)
    sessions = []
    failure_modes = {}
    successful_prints = 0
    for s in last_sessions:
        sessions.append({
            "user": s.user.full_name if s.user else "Unknown",
            "time_since": (datetime.now() - s.start_time)
        })
        for p in s.print_records:
            if p.successful:
                successful_prints += 1
            if p.failure_mode != PrintRecord.FailureModeEnum.NO_FAILURE:
                failure_modes[p.failure_mode.value] = failure_modes.get(p.failure_mode, 0) + 1
    success_rate = round((successful_prints / total_prints) * 100, 2) if total_prints > 0 else 0

    return render_template(
        "partials/session_summary_modal.html",
        session=session,
        session_summary={
            "time_since_film_change": (datetime.now() - time_since_film_change.start_time) if time_since_film_change else None,
            "time_since_calibration": (datetime.now() - time_since_calibration.calibration_date) if time_since_calibration else None,
            "last_sessions": sessions,
            "successful_prints": successful_prints,
            "total_prints": total_prints,
            "success_rate": success_rate,
            "failure_modes": failure_modes
        }
    )


@blueprint.route(
    "/users/register_user",
    methods=["GET"],
)
def register_user_get():
    edit = request.args.get("edit", "false").lower() == "true"
    edit_user_id = request.args.get("user_id", None)
    edit_user_id = int(edit_user_id) if edit_user_id is not None else None
    log.info("Register user GET request: edit=%s, edit_user_id=%s", edit, edit_user_id)

    ctx = get_auth_context()
    ctx_user = ctx.get("user", None)
    ctx_admin = ctx.get("permissions", {}).get("admin", False)
    log.info(ctx)

    form = RegisterForm()
    if edit and (ctx_user.id == edit_user_id or ctx_admin):
        log.info("Editing user with ID: %s", edit_user_id)
        user = User.query.get(edit_user_id)
        form.edit.data = "true"
        form.edit_user_id.data = str(user.id)
        form.first_name.data = user.first_name
        form.last_name.data = user.last_name
        form.email.data = user.email
        form.username.data = user.username
        form.password.data = user.password[0:20]  # pre-fill with first 20 characters of password hash for security

    return render_template(
        "partials/register_user_modal.html",
        register_form=form,
    )


@blueprint.route(
    "/users/register_user",
    methods=["POST"],
)
def register_user_post():
    register_form = RegisterForm()

    edit = register_form.edit.data.lower() == "true"
    edit_user_id = register_form.edit_user_id.data if edit else None
    edit_user_id = int(edit_user_id) if edit_user_id is not None else None

    ctx = get_auth_context()
    ctx_user = ctx.get("user", None)
    ctx_admin = ctx.get("permissions", {}).get("admin", False)

    if not (Config.OPEN_REGISTRATION or (edit and (ctx_user.id == edit_user_id or ctx_admin))):
        # check if user is logged in and has admin permissions
        is_admin = False
        if current_user.is_authenticated:
            is_admin = current_user.admin_permissions
        if not is_admin:
            return jsonify({"success": False, "errors": {"username": ["Access denied. You do not have permission to register users."]}})

    
    if not register_form.validate():
        return jsonify({"success": False, "errors": register_form.errors})
    
    if edit:
        user = User.query.get(edit_user_id)
        user.first_name = register_form.first_name.data
        user.last_name = register_form.last_name.data
        user.email = register_form.email.data
        user.username = register_form.username.data

        if register_form.first_name.data and register_form.last_name.data:
            user.full_name = register_form.first_name.data + " " + register_form.last_name.data
        elif register_form.first_name.data:
            user.full_name = register_form.first_name.data
        elif register_form.last_name.data:
            user.full_name = register_form.last_name.data
        else:
            user.full_name = None

        if register_form.password.data and str(user.password[0:20]) != register_form.password.data:
            user.set_password(register_form.password.data)

        user.save()
        log.info("%s updated their information", user.full_name)

    else:
        user = User(
            first_name=register_form.first_name.data,
            last_name=register_form.last_name.data,
            email=register_form.email.data,
            username=register_form.username.data,
            password=register_form.password.data,
        )
        
        # set new user permission based on "default" user
        default_user = User.query.filter_by(username="default").first()
        user.print_permissions = default_user.print_permissions
        user.calibration_permissions = default_user.calibration_permissions
        user.advanced_permissions = default_user.advanced_permissions
        user.admin_permissions = default_user.admin_permissions

        user.save()
        log.info("%s registered as %s", user.full_name, user.username)

    return jsonify({"success": True})


@blueprint.route(
    "/users/start_session",
    methods=["GET"],
)
@require_permissions(require_session=False)
def start_session_get():
    return render_template(
        "partials/start_session_modal.html",
        start_session_form=StartSessionForm()
    )

@blueprint.route(
    "/users/start_session",
    methods=["POST"],
)
@require_permissions(require_session=False)
def start_session_post():
    start_form = StartSessionForm()
    if not start_form.validate():
        return jsonify({"success": False, "errors": start_form.errors})

    existing = Session.get_active_session()

    if existing:
        msg = "Printer already in use by %s" % existing.user.full_name
        log.info(msg)
        return jsonify({"success": False, "errors": {"password": [msg]}})

    # check if user has an unended session (end time not set)
    previous_session = Session.query.filter_by(user_id=start_form.user.id).order_by(Session.start_time.desc()).first()
    if previous_session and previous_session.end_time is None:
        return jsonify({"success": False, "errors": {"password": ["Your previous session's logs are incomplete. Please complete your previous session before starting a new one."], "session_id": previous_session.id}})

    session = Session(
        user=start_form.user,
        start_time=datetime.now(),
    )
    session.save()
    log.info("%s started session", start_form.user.full_name)

    socketio.emit("session_started", {"id": session.id, "user": session.user.full_name, "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, namespace="/global")

    return jsonify({"success": True})


@blueprint.route(
    "/users/reset_code",
    methods=["GET"],
)
def reset_code_get():
    from printer_server.app import send_email
    username = request.args.get("username")
    user = User.query.filter_by(username=username).first()
    token = None
    if not user:
        msg = "User not found for username: %s" % username
        log.warning(msg)
        return jsonify({"success": False, "errors": {"username": [msg]}})
    token, otc = user.generate_token()
    send_email(
        recipient=user.email,
        subject="Password Reset Code",
        body_html=f"""
            <html>
                <body>
                    <p>Your password reset code is: <b>{otc}</b></p>
                    <p>This code will expire in 10 minutes.</p>
                    <p>If you did not request a password reset, please ignore this email.</p>
                </body>
            </html>
        """
    )
    form = ResetCodeForm(username=username, token=token)
    return render_template(
        "partials/forgot_password_code_modal.html",
        verify_reset_code_form=form
    )


@blueprint.route(
    "/users/reset_code",
    methods=["POST"],
)
def reset_code_post():
    reset_form = ResetCodeForm()
    if not reset_form.validate():
        return jsonify({"success": False, "errors": reset_form.errors})
    # generate new reset token
    reset_form.user.generate_token(need_otc=False)
    return jsonify({"success": True, "token": reset_form.user.token})


@blueprint.route(
    "/users/reset_password",
    methods=["GET"],
)
def reset_password_get():
    user_id = request.args.get("id")
    user_id = int(user_id) if user_id is not None else None
    username = request.args.get("username")
    token = request.args.get("token")

    # lookup username if user_id is provided
    if user_id:
        user = User.query.get(user_id)
        if not user:
            msg = "Invalid user ID: %s" % user_id
            log.warning(msg)
            return jsonify({"success": False, "errors": {"username": [msg]}})
        username = user.username
    elif username:
        user = User.query.filter_by(username=username).first()
        if not user:
            msg = "Invalid username: %s" % username
            log.warning(msg)
            return jsonify({"success": False, "errors": {"username": [msg]}})
    
    # If session user is the same as the username in the request, generate a new reset token without requiring OTC
    ctx = get_auth_context()
    ctx_user = ctx.get("user", None)
    ctx_authenticated = ctx.get("authenticated", False)
    ctx_admin = ctx.get("permissions", {}).get("admin", False)

    if ctx_user and ctx_user.username == username:
        user.generate_token(need_otc=False)
        token = user.token

    # If current user has admin permission generate token
    if ctx_authenticated and ctx_admin:
        user.generate_token(need_otc=False)
        token = user.token

    if not token:
        msg = "Missing token for password reset"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})

    user = User.query.filter_by(token=token).first()

    if not user:
        msg = "Invalid token for password reset"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})
    if user.token_expiration < datetime.now():
        msg = "Token has expired for password reset"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})
    if user.reset_otc is not None:
        msg = "Requires one-time code verification"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})

    return render_template(
        "partials/forgot_password_modal.html",
        reset_password_form=ResetPasswordForm(username=user.username, token=token),
    )

@blueprint.route(
    "/users/reset_password",
    methods=["POST"],
)
def reset_password_post():
    reset_form = ResetPasswordForm()
    if not reset_form.validate():
        return jsonify({"success": False, "errors": reset_form.errors})

    user = reset_form.user
    user.clear_token()
    user.set_password(reset_form.password.data)
    user.save()
    log.info("%s reset password", user.full_name)

    return jsonify({"success": True})


@blueprint.route("/users/delete_user", methods=["GET"])
@require_permissions(require_session=False)
def delete_user_get():
    user_id = request.args.get("user_id")
    token = None

    user = User.query.get(user_id)
    if not user:
        msg = "Invalid user ID: %s" % user_id
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})

    # If session user is the same as in the request, generate a new reset token
    ctx = get_auth_context()
    ctx_user = ctx.get("user", None)
    ctx_authenticated = ctx.get("authenticated", False)
    ctx_admin = ctx.get("permissions", {}).get("admin", False)

    if ctx_user and ctx_user.username == user.username:
        log.info("%s requested to delete their own account, generating reset token", ctx_user.full_name)
        user.generate_token(need_otc=False)
        token = user.token

    # If current user has admin permission generate token
    if ctx_authenticated and ctx_admin:
        user.generate_token(need_otc=False)
        token = user.token

    if not token:
        msg = "Insufficient permissions to delete user"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})

    return {"success": True, "token": token}


@blueprint.route("/users/delete_user", methods=["POST"])
@require_permissions(require_session=False)
def delete_user_post():
    user_id = request.args.get("user_id")
    token = request.args.get("token")

    if not user_id:
        msg = "Missing user ID for deletion"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"user_id": [msg]}})
    user = User.query.get(user_id)
    if not user:
        msg = "Invalid user ID for deletion: %s" % user_id
        log.warning(msg)
        return jsonify({"success": False, "errors": {"user_id": [msg]}})

    if not token:
        msg = "Missing token for user deletion"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})
    if user.token != token:
        msg = "Insufficient permissions for user deletion"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})
    if user.token_expiration < datetime.now():
        msg = "Token has expired for user deletion"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})

    log.info("Deleted user %s", user.full_name)

    # stop session if user is currently in a session
    active_session = Session.query.filter_by(user_id=user.id, active=True).first()
    if active_session:
        end_session_timeout(active_session.id)
    user.delete()
    return jsonify({"success": True})


@blueprint.route("/users/change_permission", methods=["GET"])
@require_permissions(require_session=False)
def change_permission_get():
    user_id = request.args.get("id")
    user_id = int(user_id) if user_id is not None else None
    token = None

    user = User.query.get(user_id)
    if not user:
        msg = "Invalid user ID: %s" % user_id
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})

    # If current user has admin permission generate token
    if current_user.is_authenticated and current_user.admin_permissions:
        user.generate_token(need_otc=False)
        token = user.token

    if not token:
        msg = "Insufficient permissions to change user permissions"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})

    return {"success": True, "token": token}

@blueprint.route("/users/change_permission", methods=["POST"])
@require_permissions(require_session=False)
def change_permission_post():
    user_id = request.args.get("id")
    token = request.args.get("token")
    permission = request.args.get("permission")
    value = request.args.get("value", "false").lower() == "true"

    if not user_id:
        msg = "Missing user ID for permission change"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"user_id": [msg]}})
    user = User.query.get(user_id)
    if not user:
        msg = "Invalid user ID for permission change: %s" % user_id
        log.warning(msg)
        return jsonify({"success": False, "errors": {"user_id": [msg]}})

    if not token:
        msg = "Missing token for permission change"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})
    if user.token != token:
        msg = "Insufficient permissions for permission change"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})
    if user.token_expiration < datetime.now():
        msg = "Token has expired for permission change"
        log.warning(msg)
        return jsonify({"success": False, "errors": {"token": [msg]}})

    if permission == "print":
        user.print_permissions = value
    elif permission == "calibration":
        user.calibration_permissions = value
    elif permission == "advanced":
        user.advanced_permissions = value
    elif permission == "admin":
        user.admin_permissions = value
    else:
        msg = "Invalid permission: %s" % permission
        log.warning(msg)
        return jsonify({"success": False, "errors": {"permission": [msg]}})
    user.save()

    return jsonify({"success": True, "permission": permission, "value": value})


@blueprint.route("/users/print_form")
@require_permissions(require_session=False)
def print_form():
    def fill_print_form(idx, print_record):
        print_form = EndPrintForm(prefix=f"prints-{idx}")
        print_form.print_id.data = print_record.id
        print_form.print_name.data = print_record.original_filename
        print_form.start_time.data = print_record.start_time
        print_form.end_time.data = print_record.end_time
        print_form.incomplete.data = "" if print_record.completed else "Incomplete"
        if print_record.successful is None:
            print_form.successful.data = ""
        elif print_record.successful:
            print_form.successful.data = "yes"
        else:
            print_form.successful.data = "no"
            print_form.failure_mode.data = print_record.failure_mode.name if print_record.failure_mode != PrintRecord.FailureModeEnum.NO_FAILURE else ""
        print_form.logged.data = print_record.logged
        print_form.failure_detail.data = print_record.other_failure_mode
        print_form.print_notes.data = print_record.notes
        return print_form

    print_id = request.args.get("print_id")
    session_id = request.args.get("session_id")

    if (not print_id and not session_id):
        log.warning("Invalid request: print_id and session_id are both missing")
        return jsonify({
            "success": False, 
            "errors": {
                "print_id": ["Invalid print ID"], 
                "session_id": ["Invalid session ID"]
                }
            })
    elif (print_id and session_id):
        log.warning("Invalid request: print_id and session_id are both present")
        return jsonify({
            "success": False, 
            "errors": {
                "print_id": ["Incompatible with session ID"], 
                "session_id": ["Incompatible with print ID"]
                }
            })
    elif print_id:
        print_record = PrintRecord.query.get(print_id)
        return render_template(
            "partials/end_print_modal.html", 
            print_forms=[fill_print_form(0, print_record)]
        )
    elif session_id:
        print_records = PrintRecord.query.filter_by(session_id=session_id).all()
        return render_template(
            "partials/print_form.html", 
            print_forms=[fill_print_form(i, p) for i, p in enumerate(print_records)]
        )


@blueprint.route(
    "/users/end_print/<print_id>",
    methods=["POST"],
)
@require_permissions(require_session=False)
def end_print_post(print_id):
    end_print_form = EndPrintForm(prefix=f"prints-0")
    print_record = PrintRecord.query.get(print_id)
    later = request.args.get('later', "false", type=str) == "true"

    if not print_record:
        return jsonify({"success": False, "errors": {"print_id": ["Invalid print ID"]}})

    if not later:
        if not end_print_form.validate():
            return jsonify({"success": False, "errors": {"prints": [end_print_form.errors]}})
        print_record.logged = True
    
    if end_print_form.successful.data == "no":
        print_record.successful = False
        print_record.failure_mode = end_print_form.failure_mode.data if end_print_form.failure_mode.data else "NO_FAILURE"
        if end_print_form.failure_mode.data == "OTHER_FAILURE":
            print_record.other_failure_mode = end_print_form.failure_detail.data if end_print_form.failure_detail.data else None
        else:
            print_record.other_failure_mode = None
    elif end_print_form.successful.data == "yes":
        print_record.successful = True
        print_record.failure_mode = "NO_FAILURE"
        print_record.other_failure_mode = None
    else:
        print_record.successful = None
        print_record.failure_mode = "NO_FAILURE"
        print_record.other_failure_mode = None

    print_record.notes = end_print_form.print_notes.data if end_print_form.print_notes.data else None
    
    print_record.save()

    return jsonify({"success": True})


@blueprint.route(
    "/users/end_session/<session_id>",
    methods=["GET"],
)
@require_permissions(require_session=False)
def end_session_get(session_id):
    end_session_form = EndSessionForm()
    session = Session.query.get(session_id)

    if session:
        end_session_form.film_changed.data = session.film_changed
        end_session_form.printer_issues.data = session.hardware_issues
        end_session_form.printer_issue_details.data = session.hardware_issues_details if session.hardware_issues else None
        end_session_form.session_notes.data = session.notes

    return render_template(
        "partials/end_session_modal.html",
        end_session_form=end_session_form
    )


timeout_email_msg = {
    "head": "Printer Session Ended (Logs Required)",
    "body": f"""
        <html>
            <body>
                <p>Your session has been ended on the <b>{Config.HOSTNAME}</b> printer at <b>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</b>, but the required print logs have not yet been completed.</p>

                <p>Please complete the logs as soon as possible.</p>

                <ul>
                <li>Access them via <b>{Config.HOSTNAME} → </b> Print History → Sessions</li>
                <li>You cannot start a new session until logs are complete</li>
                </ul>

                <p>Thank you.</p>
            </body>
        </html>
    """
}

@blueprint.route(
    "/users/end_session_timeout/<session_id>",
    methods=["POST"],
)
def end_session_timeout(session_id):
    session = Session.query.get(session_id)

    # Send an email to the user
    from printer_server.app import send_email
    send_email(
        recipient=session.user.email,
        subject=timeout_email_msg["head"],
        body_html=timeout_email_msg["body"]
    )

    # Update print information
    prints = session.print_records
    prints_successful = 0
    for print_record in prints:
        if print_record.successful:
            prints_successful += 1

    # Update calibration information (query all calibration records between start and end of session (last print) and remove all but the latest)
    calibrations = None
    if Calibration.query.order_by(Calibration.calibration_date.desc()).first() is not None:
        calibrations = Calibration.query.filter(
            Calibration.calibration_date >= session.start_time,
            Calibration.calibration_date <= (datetime.now() if len(prints) == 0 else prints[-1].start_time + timedelta(seconds=10))
        ).all()

    if calibrations:
        # Keep only the last calibration during the session
        latest_calibration = max(calibrations, key=lambda x: x.calibration_date)
        # # Remove all other calibrations
        # for calibration in calibrations:
        #     if calibration != latest_calibration:
        #         calibration.delete()
    else:
        # no calibrations done during session. Set to the last calibration done before session started
        latest_calibration = Calibration.query.filter(
            Calibration.calibration_date < session.start_time
        ).order_by(Calibration.calibration_date.desc()).first()

        # fallback to the most recent calibration
        if not latest_calibration: 
            latest_calibration = Calibration.query.order_by(Calibration.calibration_date.desc()).first()

    # Update session information
    if session:
        session.active = False
        session.prints_successful = prints_successful
        session.calibration_data = latest_calibration
        session.save()

        log.info("%s session timed out", session.user.full_name)
            
    socketio.emit("session_ended", namespace="/global")

    # if was called via route, return JSON response
    if request.path.startswith("/users/end_session_timeout/"):
        return jsonify({"success": True})

@blueprint.route(
    "/users/end_session/<session_id>",
    methods=["POST"],
)
@require_permissions(require_session=False)
def end_session_post(session_id):
    end_session_form = EndSessionForm()
    later = request.args.get('later', "false", type=str) == "true"
    session = Session.query.get(session_id)

    if later:
        # Send an email to the user
        from printer_server.app import send_email
        send_email(
            recipient=session.user.email,
            subject=timeout_email_msg["head"],
            body_html=timeout_email_msg["body"]
        )
    else:
        if not end_session_form.validate():
            return jsonify({"success": False, "errors": end_session_form.errors})

    # Update print information
    prints = session.print_records
    prints_successful = 0
    for print_record in prints:
        # lookup print in form prints
        end_print_form = next((p for p in end_session_form.prints if int(p.print_id.data) == int(print_record.id)), None)
        if not end_print_form:
            continue

        if not later:
            print_record.logged = True
        
        if end_print_form.successful.data == "no":
            print_record.successful = False
            print_record.failure_mode = end_print_form.failure_mode.data if end_print_form.failure_mode.data else "NO_FAILURE"
            if end_print_form.failure_mode.data == "OTHER_FAILURE":
                print_record.other_failure_mode = end_print_form.failure_detail.data if end_print_form.failure_detail.data else None
            else:
                print_record.other_failure_mode = None
        elif end_print_form.successful.data == "yes":
            prints_successful += 1
            print_record.successful = True
            print_record.failure_mode = "NO_FAILURE"
            print_record.other_failure_mode = None
        else:
            print_record.successful = None
            print_record.failure_mode = "NO_FAILURE"
            print_record.other_failure_mode = None

        print_record.notes = end_print_form.print_notes.data if end_print_form.print_notes.data else None
        
        print_record.save()

    
    # Update calibration information (query all calibration records between start and end of session (last print) and remove all but the latest)
    calibrations = None
    if Calibration.query.order_by(Calibration.calibration_date.desc()).first() is not None:
        calibrations = Calibration.query.filter(
            Calibration.calibration_date >= session.start_time,
            Calibration.calibration_date <= (datetime.now() if len(prints) == 0 else prints[-1].start_time + timedelta(seconds=10))
        ).all()

    if calibrations:
        # Keep only the last calibration during the session
        latest_calibration = max(calibrations, key=lambda x: x.calibration_date)
        # # Remove all other calibrations
        # for calibration in calibrations:
        #     if calibration != latest_calibration:
        #         calibration.delete()
    else:
        # no calibrations done during session. Set to the last calibration done before session started
        latest_calibration = Calibration.query.filter(
            Calibration.calibration_date < session.start_time
        ).order_by(Calibration.calibration_date.desc()).first()

        # fallback to the most recent calibration
        if not latest_calibration: 
            latest_calibration = Calibration.query.order_by(Calibration.calibration_date.desc()).first()


    # Update session information
    if session:
        session.active = False
        if not later:
            session.end_time = datetime.now() if len(prints) == 0 else prints[-1].start_time + timedelta(seconds=10)
        session.prints_successful = prints_successful
        session.film_changed = end_session_form.film_changed.data
        session.hardware_issues = end_session_form.printer_issues.data
        session.hardware_issues_details = end_session_form.printer_issue_details.data if end_session_form.printer_issues.data == True else None
        session.notes = end_session_form.session_notes.data
        session.calibration_data = latest_calibration
        session.save()

        log.info("%s ended session", session.user.full_name)
            
    socketio.emit("session_ended", namespace="/global")

    return jsonify({"success": True})


@socketio.on("connect", namespace="/global")
@socket_require_permissions(require_session=False)
def connect():
    emit(
        "connected",
        dict(),
        namespace="/global",
        broadcast=False,
    )


@socketio.on("disconnect", namespace="/global")
def disconnect():
    log.debug("Socket disconnected %s", request.sid)
