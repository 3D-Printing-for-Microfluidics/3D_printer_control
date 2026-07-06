import os
import shutil
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, flash, send_file, jsonify


from printer_server.settings import Config
from printer_server.extensions import socketio, db
from printer_server.views.table import *
from printer_server.models import PrintRecord, PrintQueue, Session, User
from printer_server.hardware_configuration.hardware_configuration import config_dict
from printer_server.print_file_validator import validate_schema, validate_printer_compatibility
from printer_server.views.users import get_auth_context
from printer_server.views.users import require_permissions

blueprint = Blueprint(
    "print_history", __name__, url_prefix="/", static_folder="../static"
)
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def generate_session_table_column_definition():
    printer_user_options = [name for _, name in get_user_lookup()]

    user = get_auth_context().get("user", None)

    columns = [
        Column(key="col-user", name="User", value=lambda r: r.user.full_name if r.user else "", filterable="Yes", options=printer_user_options, visible=True, db_col=Session.user.has(User.full_name), db_filter=generate_nested_lambda([Session.user, User.full_name], generate_string_lambda)),
        Column(key="col-start-time", name="Start Time", value=lambda r: r.start_time, type="datetime", filterable="Yes", visible=True, db_col=Session.start_time, db_filter=generate_datetime_lambda(Session.start_time)),
        Column(key="col-end-time", name="End Time", value=lambda r: r.end_time, type="datetime", filterable="No", db_col=Session.end_time, db_filter=generate_datetime_lambda(Session.end_time)),
        Column(key="col-session-duration", name="Duration", value=lambda r: generate_duration_value(r.start_time, r.end_time), type="duration", filterable="No", visible=True, db_col=generate_duration_db_column(Session.start_time, Session.end_time), db_filter=lambda search: generate_duration_db_column(Session.start_time, Session.end_time).ilike(f"%{search}%")),
        Column(key="col-print-ratio", name="Print Ratio", value=lambda r: f"{r.prints_successful}/{len(r.print_records)}", type="text", filterable="No", visible=True, db_col=Session.total_prints_in_session),
        Column(key="col-good-prints", name="Successful Prints", value=lambda r: f"{r.prints_successful}", type="text", db_col=Session.prints_successful, db_filter=generate_string_lambda(Session.prints_successful)),
        Column(key="col-total-prints", name="Total Prints", value=lambda r: len(r.print_records), type="text", db_col=Session.total_prints_in_session, db_filter=generate_string_lambda(Session.total_prints_in_session)),
        Column(key="col-film-changed", name="Film Changed", value=lambda r: r.film_changed, type="boolean", visible=True, db_col=Session.film_changed, db_filter=generate_boolean_lambda(Session.film_changed)),
        Column(key="col-hardware-issues", name="Hardware Issues", value=lambda r: r.hardware_issues, type="boolean", visible=True, db_col=Session.hardware_issues, db_filter=generate_boolean_lambda(Session.hardware_issues)),
        Column(key="col-hardware-issues-details", name="Hardware Issues Details", value=lambda r: r.hardware_issues_details, db_col=Session.hardware_issues_details, db_filter=generate_string_lambda(Session.hardware_issues_details)),
        Column(key="col-notes", name="Notes", value=lambda r: r.notes, db_col=Session.notes, db_filter=generate_string_lambda(Session.notes)),
        Column(
            key="col-finish", 
            name="Logs", 
            type="button", 
            button_style=(lambda r: "btn btn-outline-warning" if r.end_time is None else "btn btn-outline-success"), 
            button_name=(lambda r: "Finish" if r.end_time is None else "Edit"), 
            button_class="finish-session-btn", 
            sortable=False, filterable="No", visible=True, 
            href_enabled=lambda r: r.user == user or r.end_time is None)
    ]

    def get_sort_col(column_key):
        map = {}
        for col in columns:
            if col.db_col is not None:
                map[col.key] = col.db_col
        return map.get(column_key, Session.start_time)
    
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


def generate_print_table_column_definition():
    printer_user_options = [name for _, name in get_user_lookup()]
    design_user_options = get_distinct_values(PrintRecord.design_user)
    design_resin_options = get_distinct_values(PrintRecord.design_resin)
    design_printer_options = get_distinct_values(PrintRecord.design_printer)
    design_slicer_options = get_distinct_values(PrintRecord.design_slicer)

    # upload_ip = Column(db.String(30))
    # start_ip = Column(db.String(30))

    user = get_auth_context().get("user", None)

    columns = [
        Column(key="col-name", name="Name", value=lambda r: r.original_filename, type="link", href="/print_history/download/<id>", filterable="Yes", visible=True, db_col=PrintRecord.original_filename, db_filter=generate_string_lambda(PrintRecord.original_filename)),
        Column(key="col-printer-user", name="Printer User", value=lambda r: r.user.full_name if r.user else "", filterable="Yes", options=printer_user_options, visible=True, db_col=PrintRecord.user.has(User.full_name), db_filter=generate_nested_lambda([PrintRecord.user, User.full_name], generate_string_lambda)),
        Column(key="col-start-time", name="Start Time", value=lambda r: r.start_time, type="datetime", filterable="Yes", visible=True, db_col=PrintRecord.start_time, db_filter=generate_datetime_lambda(PrintRecord.start_time)),
        Column(key="col-end-time", name="End Time", value=lambda r: r.end_time, type="datetime", filterable="No", db_col=PrintRecord.end_time, db_filter=generate_datetime_lambda(PrintRecord.end_time)),
        Column(key="col-upload-time", name="Upload Time", value=lambda r: r.upload_time, type="datetime", filterable="No", db_col=PrintRecord.upload_time, db_filter=generate_datetime_lambda(PrintRecord.upload_time)),
        Column(key="col-print-time", name="Print Time", value=lambda r: generate_duration_value(r.start_time, r.end_time), type="duration", filterable="No", visible=True, db_col=generate_duration_db_column(PrintRecord.start_time, PrintRecord.end_time), db_filter=lambda search: generate_duration_db_column(PrintRecord.start_time, PrintRecord.end_time).ilike(f"%{search}%")),
        Column(key="col-completed", name="Completed", value=lambda r: r.completed, type="boolean", visible=True, db_col=PrintRecord.completed, db_filter=generate_boolean_lambda(PrintRecord.completed)),
        Column(key="col-design-user", name="Design User", value=lambda r: r.design_user, options=design_user_options, db_col=PrintRecord.design_user, db_filter=generate_string_lambda(PrintRecord.design_user)),
        Column(key="col-design-purpose", name="Purpose", value=lambda r: r.design_purpose, db_col=PrintRecord.design_purpose, db_filter=generate_string_lambda(PrintRecord.design_purpose)),
        Column(key="col-design-description", name="Description", value=lambda r: r.design_description, db_col=PrintRecord.design_description, db_filter=generate_string_lambda(PrintRecord.design_description)),
        Column(key="col-design-resin", name="Resin", value=lambda r: r.design_resin, options=design_resin_options, db_col=PrintRecord.design_resin, db_filter=generate_string_lambda(PrintRecord.design_resin)),
        Column(key="col-design-printer", name="3D Printer", value=lambda r: r.design_printer, options=design_printer_options, db_col=PrintRecord.design_printer, db_filter=generate_string_lambda(PrintRecord.design_printer)),
        Column(key="col-design-slicer", name="Slicer", value=lambda r: r.design_slicer, options=design_slicer_options, db_col=PrintRecord.design_slicer, db_filter=generate_string_lambda(PrintRecord.design_slicer)),
        Column(key="col-design-slice-date", name="Slice Date", value=lambda r: r.design_slice_date, filterable="No", db_col=PrintRecord.design_slice_date, db_filter=generate_string_lambda(PrintRecord.design_slice_date)),
        Column(key="col-failure-mode", name="Failure Mode", value=lambda r: PrintRecord.FailureModeEnum(r.failure_mode).value if r.failure_mode is not None else "", db_col=PrintRecord.failure_mode, db_filter=generate_string_lambda(PrintRecord.failure_mode)),
        Column(key="col-failure-other", name="Other Failure Mode", value=lambda r: r.other_failure_mode, db_col=PrintRecord.other_failure_mode, db_filter=generate_string_lambda(PrintRecord.other_failure_mode)),
        Column(key="col-notes", name="Notes", value=lambda r: r.notes, db_col=PrintRecord.notes, db_filter=generate_string_lambda(PrintRecord.notes)),
        Column(key="col-reprint", name="Reprint", type="button", href="/print_history/reprint/<id>", button_style="btn-outline-info", button_name="Reprint", button_class="reprint-btn", sortable=False, filterable="No", visible=True),
        Column(key="col-log", name="Logs", type="button", button_style=(lambda r: "btn btn-outline-warning" if r.logged == False and r.session.active else "btn btn-outline-success"), button_name=(lambda r: "Finish" if r.logged == False and r.session.active else "Edit"), button_class="print-log-btn", sortable=False, filterable="No", visible=True, href_enabled=lambda r: r.user == user)
    ]

    def get_sort_col(column_key):
        map = {}
        for col in columns:
            if col.db_col is not None:
                map[col.key] = col.db_col
        return map.get(column_key, PrintRecord.start_time)
    
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


@blueprint.route("/print_history")
@require_permissions(require_session=False)
def index():
    val = request.args.get("session_view", "true").lower()
    session_view = val in ("true", "1", "yes", "on")
    
    return render_template(
        "print_history.html",
        session_view=session_view,
        hostname=Config.HOSTNAME,
    )


@blueprint.route("/print_history/print_table")
@require_permissions(require_session=False)
def print_table():
    subtable_id = request.args.get("session_id", None)
    if subtable_id is None:
        table = generate_table(
            name = "Prints",
            table_key = "print-history", 
            route = "/print_history/print_table",
            query = PrintRecord.query, 
            table_definition = generate_print_table_column_definition(),  
            has_filters = True,
            subtables = None,
            paginate = 20, 
            args = request.args
        )
    else:
        table = generate_table(
            name = "Prints",
            table_key = f"session-history-Prints-subtable-{subtable_id}",
            route = f"/print_history/print_table?session_id={subtable_id}",
            query = PrintRecord.query.filter_by(session_id=subtable_id),
            table_definition = generate_print_table_column_definition(),
            has_filters = False,
            subtables = None,
            paginate = -1, 
            args = request.args
        )

    return render_template(
        "partials/table.html",
        table=table
    )


@blueprint.route("/print_history/session_table")
@require_permissions(require_session=False)
def session_table():
    table = generate_table(
        name = "Sessions",
        table_key = "session-history",
        route = "/print_history/session_table",
        query = Session.query, 
        table_definition = generate_session_table_column_definition(),
        has_filters = True,
        subtables = {
            "Calibration": "/calibration_history/calibration_table?session_id=",
            "Prints" : "/print_history/print_table?session_id=",
        },
        paginate = 20, 
        args = request.args
    )
    

    return render_template(
        "partials/table.html",
        table=table
    )


@blueprint.route("/print_history/download/<path:job_id>", methods=["GET", "POST"])
@require_permissions(require_session=False)
def download(job_id):
    """Download the job specified by job_id."""
    file_location = os.path.join(os.path.join(Config.UPLOAD_FOLDER, "print_history"))
    job = PrintRecord.query.get_or_404(job_id)
    return send_file(
        os.path.join(file_location, job.zip_filename),
        as_attachment=True,
        download_name=job.original_filename,
    )


@blueprint.route("/print_history/reprint/<path:job_id>", methods=["GET", "POST"])
@require_permissions(require_session=True)
def add_to_queue(job_id):
    """Add the print job to the print queue."""
    # job_id = job_id.split("-")[1]
    job = PrintRecord.query.get_or_404(job_id)
    upload_time = datetime.now()
    old_filename = os.path.join(Config.UPLOAD_FOLDER, "print_history", job.zip_filename)
    new_filename = os.path.join(
        Config.UPLOAD_FOLDER,
        "queue",
        f"{upload_time.strftime('job-%Y-%m-%d_%H-%M-%S.%f')}.zip",
    )
    shutil.copyfile(old_filename, new_filename)

    try:
        print_settings, schema_ver = validate_schema(new_filename)
        if schema_ver not in config_dict["valid_schema_versions"]:
            raise ValueError(f"Printer does not support {schema_ver} JSON format")
        validate_printer_compatibility(print_settings)
        msg = f"{job.original_filename} added to print queue."
        log.info(msg)
        print_job = PrintQueue(
            original_filename=job.original_filename,
            upload_time=upload_time,
            upload_ip=job.upload_ip,
            user=Session.get_session_user()
        ).save()
        socketio.emit(
            "job uploaded",
            {
                "id": print_job.id,
                "name": job.original_filename,
                "upload_time": upload_time.strftime("%Y-%m-%d %H:%M:%S"),
                "upload_ip": request.remote_addr,
                "user_name": Session.get_session_user().full_name if Session.get_session_user() else None,
                "is_current_user": True
            },
            namespace="/printing"
        )
    except ValueError as ex:
        msg = f"Job validation failed for {job.original_filename}:\n {str(ex).strip()}"
        socketio.emit(
            "flash", {"text": msg, "category": "warning"}, namespace="/print_history"
        )
        log.info(msg)
        os.remove(new_filename)
    return '', 204
