import os
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, flash, send_file

from printer_server.settings import Config
from printer_server.models import PrintRecord

blueprint = Blueprint(
    "print_history", __name__, url_prefix="/", static_folder="../static"
)


def flash_errors(form, category="warning"):
    """Flash all errors for a form."""
    for field, errors in form.errors.items():
        for error in errors:
            flash("{0} - {1}".format(getattr(form, field).label.text, error), category)


def calculate_page_range(current_page, total_pages):
    """Calculate the page range to be displayed on the navbar.

    :param current_page: current page number
    :param total_pages: total page number
    :returns: the page number to show in pagination
    """

    # num_pages_to_display = 7

    # if current_page <= num_pages_to_display:
    #     start_page, end_page = 1, total_pages
    # elif current_page - 3 < 1:
    #     start_page, end_page = 1, num_pages_to_display
    # elif current_page + 3 > total_pages:
    #     start_page, end_page = total_pages - 6, total_pages
    # else:
    #     start_page, end_page = current_page - 3, current_page + 3

    # return start_page, end_page
    return 1, total_pages


@blueprint.route("/print_history")
def index():
    query = PrintRecord.query
    current_page = request.args.get("current_page", 1, type=int)
    today = datetime.now().strftime("%Y-%m-%d")
    one_week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    try:
        start_date = request.args.get("start", one_week_ago)
        date_list = [int(i) for i in start_date.split("-")]
        query = query.filter(PrintRecord.start_time >= datetime(*date_list))
    except ValueError:
        flash("Bad start date", category="danger")

    try:
        end_date = request.args.get("end", today)
        date_list = [int(i) for i in end_date.split("-")]
        query = query.filter(PrintRecord.start_time <= datetime(*date_list))
    except ValueError:
        flash("Bad end date", category="danger")

    print_records = query.order_by(PrintRecord.id.desc()).paginate(current_page, 1)
    start_page, end_page = calculate_page_range(current_page, print_records.pages)

    return render_template(
        "print_history.html",
        print_records=print_records,
        start_page=start_page,
        end_page=end_page,
        start_date=start_date,
        end_date=end_date,
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
