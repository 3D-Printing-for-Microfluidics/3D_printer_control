import os
import shutil
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, flash, send_file

from printer_server.models import PrintRecord, PrintQueue
from printer_server.settings import Config
from printer_server.extensions import socketio
from printer_server.print_file_validator import validate_v02

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

    try:
        start_date = request.args.get("start", today)
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

    print_records = query.order_by(PrintRecord.id.desc()).paginate(current_page, 20)
    start, end, boundaries = calculate_page_range(current_page, print_records.pages)

    return render_template(
        "print_history.html",
        print_records=print_records,
        start=start,
        end=end,
        start_date=start_date,
        end_date=end_date,
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
        attachment_filename=job.original_filename,
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
        validate_v02(new_filename)
        msg = f"{job.original_filename} added to print queue."
        log.info(msg)
        # socketio.emit(
        #     "flash", {"text": msg, "category": "success"}, namespace="/print_history"
        # )
        PrintQueue(
            original_filename=job.original_filename,
            upload_time=upload_time,
            upload_ip=job.upload_ip,
        ).save()
    except ValueError as e:
        msg = f"Job validation failed for {job.original_filename}:\n {str(e).strip()}"
        socketio.emit(
            "flash", {"text": msg, "category": "danger"}, namespace="/print_history"
        )
        log.info(msg)
        os.remove(new_filename)
    return ""
