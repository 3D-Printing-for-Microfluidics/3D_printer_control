import os
import shutil
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, flash, send_file

from printer_server.models import PrintRecord, PrintQueue, Session
from printer_server.settings import Config
from printer_server.extensions import socketio, db
from printer_server.hardware_configuration.hardware_configuration import config_dict
from printer_server.print_file_validator import validate_schema, validate_printer_compatibility

blueprint = Blueprint(
    "print_history", __name__, url_prefix="/", static_folder="../static"
)
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def calculate_page_range(current_page, total_pages):
    """Calculate the page range to be displayed on the navbar.

    :param current_page: current page number
    :param total_pages: total page number
    :returns: the page number range to show in the pagination navbar and
     whether or not to display the beginning and end page shortcuts
    """
    window_size = 7
    if total_pages <= window_size:
        return 1, total_pages, (False, False)
    start = current_page - window_size / 2
    end = current_page + window_size / 2
    if start <= 1:
        return 1, window_size, (False, True)
    if end >= total_pages:
        return total_pages - window_size + 1, total_pages, (True, False)
    return int(start) + 1, int(end), (True, True)


@blueprint.route("/print_history")
def index():
    query = PrintRecord.query
    current_page = request.args.get("current_page", 1, type=int)
    today = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    search = request.args.get("search", "", type=str).strip()
    design_user = request.args.get("design_user", "", type=str).strip()
    design_purpose = request.args.get("design_purpose", "", type=str).strip()
    design_description = request.args.get("design_description", "", type=str).strip()
    design_resin = request.args.get("design_resin", "", type=str).strip()
    design_printer = request.args.get("design_printer", "", type=str).strip()
    design_slicer = request.args.get("design_slicer", "", type=str).strip()
    design_slice_date = request.args.get("design_slice_date", "", type=str).strip()
    completed_filter = request.args.get("completed", "all", type=str).strip().lower()
    sort_by = request.args.get("sort", "start_time", type=str).strip().lower()
    sort_dir = request.args.get("dir", "desc", type=str).strip().lower()

    def get_distinct_values(column):
        return [
            row[0]
            for row in db.session.query(column)
            .filter(column.isnot(None), column != "")
            .distinct()
            .order_by(column)
            .all()
        ]

    design_user_options = get_distinct_values(PrintRecord.design_user)
    design_resin_options = get_distinct_values(PrintRecord.design_resin)
    design_printer_options = get_distinct_values(PrintRecord.design_printer)
    design_slicer_options = get_distinct_values(PrintRecord.design_slicer)

    try:
        start_date = request.args.get("start", default_start)
        dtart_date_dt = datetime(*[int(i) for i in start_date.split("-")])
        query = query.filter(PrintRecord.start_time >= dtart_date_dt)
    except ValueError:
        flash("Bad start date", category="danger")

    try:
        end_date = request.args.get("end", today)
        end_time_dt = datetime(*[int(i) for i in end_date.split("-")]) + timedelta(days=1)
        query = query.filter(PrintRecord.start_time <= end_time_dt)
    except ValueError:
        flash("Bad end date", category="danger")

    if search:
        like_value = f"%{search}%"
        query = query.filter(
            db.or_(
                PrintRecord.original_filename.ilike(like_value),
                PrintRecord.upload_ip.ilike(like_value),
                PrintRecord.start_ip.ilike(like_value),
                PrintRecord.design_user.ilike(like_value),
                PrintRecord.design_purpose.ilike(like_value),
                PrintRecord.design_description.ilike(like_value),
                PrintRecord.design_resin.ilike(like_value),
                PrintRecord.design_printer.ilike(like_value),
                PrintRecord.design_slicer.ilike(like_value),
                PrintRecord.design_slice_date.ilike(like_value),
            )
        )

    if design_user:
        query = query.filter(PrintRecord.design_user.ilike(f"%{design_user}%"))
    if design_purpose:
        query = query.filter(PrintRecord.design_purpose.ilike(f"%{design_purpose}%"))
    if design_description:
        query = query.filter(PrintRecord.design_description.ilike(f"%{design_description}%"))
    if design_resin:
        query = query.filter(PrintRecord.design_resin.ilike(f"%{design_resin}%"))
    if design_printer:
        query = query.filter(PrintRecord.design_printer.ilike(f"%{design_printer}%"))
    if design_slicer:
        query = query.filter(PrintRecord.design_slicer.ilike(f"%{design_slicer}%"))
    if design_slice_date:
        query = query.filter(PrintRecord.design_slice_date.ilike(f"%{design_slice_date}%"))

    if completed_filter in {"yes", "no"}:
        query = query.filter(PrintRecord.completed.is_(completed_filter == "yes"))

    duration_expr = db.func.coalesce(
        (db.func.julianday(PrintRecord.end_time) - db.func.julianday(PrintRecord.start_time))
        * 86400,
        0,
    )
    sort_map = {
        "name": PrintRecord.original_filename,
        "design_user": PrintRecord.design_user,
        "design_purpose": PrintRecord.design_purpose,
        "design_description": PrintRecord.design_description,
        "design_resin": PrintRecord.design_resin,
        "design_printer": PrintRecord.design_printer,
        "design_slicer": PrintRecord.design_slicer,
        "design_slice_date": PrintRecord.design_slice_date,
        "start_time": PrintRecord.start_time,
        "end_time": PrintRecord.end_time,
        "upload_time": PrintRecord.upload_time,
        "print_time": duration_expr,
        "completed": PrintRecord.completed,
    }
    sort_col = sort_map.get(sort_by, PrintRecord.start_time)
    if sort_dir == "asc":
        query = query.order_by(sort_col.asc(), PrintRecord.id.asc())
    else:
        query = query.order_by(sort_col.desc(), PrintRecord.id.desc())

    print_records = query.paginate(page=current_page, per_page=20)
    start, end, boundaries = calculate_page_range(current_page, print_records.pages)

    return render_template(
        "print_history.html",
        print_records=print_records,
        start=start,
        end=end,
        start_date=start_date,
        end_date=end_date,
        search=search,
        design_user=design_user,
        design_purpose=design_purpose,
        design_description=design_description,
        design_resin=design_resin,
        design_printer=design_printer,
        design_slicer=design_slicer,
        design_slice_date=design_slice_date,
        design_user_options=design_user_options,
        design_resin_options=design_resin_options,
        design_printer_options=design_printer_options,
        design_slicer_options=design_slicer_options,
        completed_filter=completed_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        boundaries=boundaries,
        hostname=Config.HOSTNAME,
    )


@blueprint.route("/print_history/<path:job_id>", methods=["GET", "POST"])
def download(job_id):
    """Download the job specified by job_id."""
    file_location = os.path.join(os.path.join(Config.UPLOAD_FOLDER, "print_history"))
    job = PrintRecord.query.get_or_404(job_id)
    return send_file(
        os.path.join(file_location, job.zip_filename),
        as_attachment=True,
        download_name=job.original_filename,
    )


@socketio.on("add_to_queue", namespace="/print_history")
def add_to_queue(job_id):
    """Add the print job to the print queue."""
    job_id = job_id.split("-")[1]
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
                "user": Session.get_session_user().full_name if Session.get_session_user() else None,
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
    return ""
