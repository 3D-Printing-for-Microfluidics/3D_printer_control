import os
from datetime import datetime
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


def calcPageNum(currentPage, totalPage):
    """Default the max page shown being 9.

    :param currentPage: current page number
    :param totalPage: total page number
    :returns: the page number to show in pagination
    """
    if currentPage <= 7:
        startPage, endPage = 1, totalPage
    elif currentPage - 3 < 1:
        startPage, endPage = 1, 7
    elif currentPage + 3 > totalPage:
        startPage, endPage = totalPage - 6, totalPage
    else:
        startPage, endPage = currentPage - 3, currentPage + 3

    return startPage, endPage


@blueprint.route("/print_history")
def index():
    page = request.args.get("page", 1, type=int)

    _PR = PrintRecord
    _q = _PR.query

    try:
        startDate = request.args.get("start", "")
        if startDate:
            temp = [int(i) for i in startDate.split("-")]
            _startDate = datetime(*temp)
            _startDate = datetime(*temp)
            _q = _q.filter(_PR.start_time >= _startDate)

    except ValueError:
        flash("Incorrect start date", category="danger")

    try:
        endDate = request.args.get("end", "")
        if endDate:
            temp = [int(i) for i in endDate.split("-")]
            _endDate = datetime(*temp)
            _q = _q.filter(_PR.start_time <= _endDate)
    except ValueError:
        flash("Incorrect end date", category="danger")

    recs = _q.order_by(_PR.id.desc()).paginate(page, 50)
    startPage, endPage = calcPageNum(page, recs.pages)

    return render_template(
        "print_history.html",
        recs=recs,
        startPage=startPage,
        endPage=endPage,
        startDate=startDate,
        endDate=endDate,
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
