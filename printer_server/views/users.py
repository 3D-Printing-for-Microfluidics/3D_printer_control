import os
import shutil
import logging
from flask_socketio import emit
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, jsonify, flash, send_file


from printer_server.settings import Config
from printer_server.extensions import socketio, db
from printer_server.views.table import *
from printer_server.forms import StartSessionForm, RegisterForm, EndSessionForm, EndPrintForm
from printer_server.models import PrintRecord, PrintQueue, Session, User, Calibration
from printer_server.hardware_configuration.hardware_configuration import config_dict
from printer_server.print_file_validator import validate_schema, validate_printer_compatibility

blueprint = Blueprint(
    "users", __name__, url_prefix="/", static_folder="../static"
)
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# login required
# session required (also requires login)

# def conditional_login(f, permissions):
#     @functools.wraps(f)
#     def decorated_function(*args, **kwargs):
#         token = request.args.get("token", None)
#         # Check if user is signed in (users always have general permissions)
#         if current_user.is_authenticated:
#             # check db to see if user has the required permissions
#             if :
#                 return f(*args, **kwargs)
#             pass
#         # Check if no_user has general permissions
#         elif 
#             return f(*args, **kwargs)

#         return login_required(f)(*args, **kwargs)
#     return decorated_function

# def conditional_socketio(f, permissions):
#     @functools.wraps(f)
#     def wrapper(*args, **kwargs):
#         return f(*args, **kwargs)
#     return wrapper

def generate_user_table_column_definition():
    user = Session.get_session_user()
    if user is None:
        user = False
    else:
        user = user.id

    columns = [
        Column(key="col-username", name="Username", value=lambda r: r.username, filterable="Yes", visible=True, db_col=User.username, db_filter=generate_string_lambda(User.username)),
        Column(key="col-email", name="Email", value=lambda r: r.email, visible=True, db_col=User.email, db_filter=generate_string_lambda(User.email)),
        Column(key="col-created-at", name="Created At", value=lambda r: r.created_at, type="datetime", db_col=User.created_at, db_filter=generate_datetime_lambda(User.created_at)),
        Column(key="col-first-name", name="First Name", value=lambda r: r.first_name, db_col=User.first_name, db_filter=generate_string_lambda(User.first_name)),
        Column(key="col-last-name", name="Last Name", value=lambda r: r.last_name, db_col=User.last_name, db_filter=generate_string_lambda(User.last_name)),
        Column(key="col-full-name", name="Full Name", value=lambda r: r.full_name, filterable="Yes", visible=True, db_col=User.full_name, db_filter=generate_string_lambda(User.full_name)),
        Column(key="col-print-permissions", name="Print Permissions", value=lambda r: r.print_permissions, type="checkbox", href_enabled=False, visible=True, db_col=User.print_permissions, db_filter=generate_boolean_lambda(User.print_permissions), vertical_header=True),
        Column(key="col-calibration-permissions", name="Calibration Permissions", value=lambda r: r.calibration_permissions, type="checkbox", href_enabled=False, visible=True, db_col=User.calibration_permissions, db_filter=generate_boolean_lambda(User.calibration_permissions), vertical_header=True),
        Column(key="col-advanced-permissions", name="Advanced Permissions", value=lambda r: r.advanced_permissions, type="checkbox", href_enabled=False, visible=True, db_col=User.advanced_permissions, db_filter=generate_boolean_lambda(User.advanced_permissions), vertical_header=True),
        Column(key="col-admin-permissions", name="Admin Permissions", value=lambda r: r.admin_permissions, type="checkbox", href_enabled=False, visible=True, db_col=User.admin_permissions, db_filter=generate_boolean_lambda(User.admin_permissions), vertical_header=True),
        Column(key="col-reset", name="Reset Password", type="button", href="/users/reset/<id>", href_enabled=lambda r: r.id == user, button_style="btn-outline-warning", button_name="Reset", button_class="reset-btn", sortable=False, filterable="No", visible=True),
        Column(key="col-delete", name="Delete User", type="button", href="/users/delete/<id>", href_enabled=lambda r: r.id == user, button_style="btn-outline-danger", button_name="Delete", button_class="delete-btn", sortable=False, filterable="No", visible=True)
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
def index():
    return render_template(
        "users.html",
        hostname=Config.HOSTNAME,
    )


@blueprint.route("/users/user_table")
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


@blueprint.route(
    "/users/register_user",
    methods=["GET"],
)
def register_user_get():
    return render_template(
        "partials/register_user_modal.html",
        register_form=RegisterForm(),
    )


@blueprint.route(
    "/users/register_user",
    methods=["POST"],
)
def register_user_post():
    register_form = RegisterForm()

    if not register_form.validate():
        return jsonify({"success": False, "errors": register_form.errors})
    
    user = User(
        first_name=register_form.first_name.data,
        last_name=register_form.last_name.data,
        email=register_form.email.data,
        username=register_form.username.data,
        password=register_form.password.data,
    )
    user.save()
    log.info("%s registered as %s", user.full_name, user.username)

    return jsonify({"success": True})


@blueprint.route(
    "/users/start_session",
    methods=["GET"],
)
def start_session_get():
    return render_template(
        "partials/start_session_modal.html",
        start_session_form=StartSessionForm()
    )

@blueprint.route(
    "/users/start_session",
    methods=["POST"],
)
def start_session_post():
    start_form = StartSessionForm()
    if not start_form.validate():
        return jsonify({"success": False, "errors": start_form.errors})

    existing = Session.get_active_session()

    if existing:
        log.info("Printer already in use by %s", existing.user.full_name)
        return jsonify({"success": False, "errors": {"user": ["Printer already in use"]}})
    
    session = Session(
        user=start_form.user,
        start_time=datetime.now(),
    )
    session.save()
    log.info("%s started session", start_form.user.full_name)

    socketio.emit("session_started", {"id": session.id, "user": session.user.full_name, "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, namespace="/users")

    return jsonify({"success": True})


@blueprint.route("/users/print_form")
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
def end_print_post(print_id):
    end_print_form = EndPrintForm(prefix=f"prints-0")
    print_record = PrintRecord.query.get(print_id)
    later = request.args.get('later', "false", type=str) == "true"

    if not print_record:
        log.warning(f"Invalid print ID: {print_id}")
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


@blueprint.route(
    "/users/end_session/<session_id>",
    methods=["POST"],
)
def end_session_post(session_id):
    end_session_form = EndSessionForm()
    later = request.args.get('later', "false", type=str) == "true"
    session = Session.query.get(session_id)

    if later:
        from printer_server.app import send_email

        head = f"Printer Session Ended (Logs Required)"
        body = f"""
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

        # # Send an email to the user
        # send_email(
        #     recipient=session.user.email,
        #     subject=head,
        #     body_html=body
        # )
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
        # Remove all other calibrations
        for calibration in calibrations:
            if calibration != latest_calibration:
                calibration.delete()
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
            
    socketio.emit("session_ended", namespace="/users")

    return jsonify({"success": True})


@socketio.on("connect", namespace="/users")
def connect():
    emit(
        "connected",
        dict(),
        namespace="/users",
        broadcast=False,
    )


@socketio.on("disconnect", namespace="/users")
def disconnect():
    log.debug("Socket disconnected %s", request.sid)
