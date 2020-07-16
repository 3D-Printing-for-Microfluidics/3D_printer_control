import os
import time
import glob
import shutil
import threading
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, render_template, flash

from printer_server.settings import Config
from printer_server.hardware_configuration import hardware_driver_handles

# from printer_server.print_settings import print_settings
from printer_server.print_file_validator import validate_v02
from printer_server.models import PrintQueue, PrintRecord
from printer_server.extensions import db, socketio

# Create bluprint
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


# @blueprint.route("/print_history")
# def index():
#     allJobs = PrintQueue.query.all()
#     return render_template("printing.html", allJobs=allJobs)


@blueprint.route("/print_history")
def printHistroy():
    page = request.args.get("page", 1, type=int)

    _PR = PrintRecord
    _q = _PR.query
    print(_q)

    # startDate = "2020-01-01"
    # # endDate = datetime(2020, month=12, day=1)
    # endDate = "2020-12-31"

    try:
        startDate = request.args.get("start", "")
        if startDate:
            temp = [int(i) for i in startDate.split("-")]
            _startDate = datetime(*temp)
            _startDate = datetime(*temp)
            _q = _q.filter(_PR.start_time >= _startDate)
        print(_q)

    except ValueError:
        flash("Incorrect start date", category="danger")

    try:
        endDate = request.args.get("end", "")
        if endDate:
            temp = [int(i) for i in endDate.split("-")]
            _endDate = datetime(*temp)
            _q = _q.filter(_PR.start_time <= _endDate)
            print(_q)
    except ValueError:
        flash("Incorrect end date", category="danger")

    recs = _q.order_by(_PR.id.desc()).paginate(page, 50)
    startPage, endPage = calcPageNum(page, recs.pages)
    print("TOTAL", recs.total)
    # print("TOTAL", recs.items)
    for record in recs.items:
        print(
            record,
            record.original_filename,
            record.upload_time,
            record.upload_time,
            record.start_ip,
            record.start_time,
            record.end_time,
            record.completed,
        )

    print(f"LOTS O STUFF\n{recs}\n{startPage}\n{endPage}\n{startDate}\n{endDate}\nDONE")
    return render_template(
        "print_history.html",
        recs=recs,
        startPage=startPage,
        endPage=endPage,
        startDate=startDate,
        endDate=endDate,
    )


@blueprint.route("archive")
def archive():
    page = request.args.get("page", 1, type=int)

    _PR = PrintRecord
    _q = _PR.query

    try:
        startDate = request.args.get("start", "")
        if startDate:
            temp = [int(i) for i in startDate.split("-")]
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
        "archive.html",
        recs=recs,
        startPage=startPage,
        endPage=endPage,
        startDate=startDate,
        endDate=endDate,
    )
