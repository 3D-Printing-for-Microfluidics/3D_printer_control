import os
import time
import glob
import shutil
import threading
import random
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, render_template

from printer_server.settings import Config
from printer_server.hardware_configuration import hardware_driver_handles

# from printer_server.print_settings import print_settings
from printer_server.print_file_validator import validate_v02
from printer_server.models import PrintQueue, PrintRecord
from printer_server.extensions import db, socketio

blueprint = Blueprint("chart", __name__, url_prefix="/", static_folder="../static")


@blueprint.route("/chart")
def index():
    return render_template("chart.html")


@socketio.on("connect", namespace="/chart")
def connect():
    print("you connected!")
    for _ in range(60):
        msg = random.randint(0, 10)
        print("emit", msg)
        socketio.emit("new_data", {"data": msg}, namespace="/chart")
        time.sleep(1)
