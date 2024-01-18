import os
import time
import pstats
import logging
from pathlib import Path, PurePath
from flask import Blueprint, render_template, send_file

from printer_server.settings import Config

blueprint = Blueprint("server_logs", __name__, url_prefix="/", static_folder="../static")
logs_folder = Path(Config.PROJECT_ROOT) / "logs"
log = logging.getLogger(__name__)
time_fmt = "%Y-%m-%d %H:%M:%S"
log.setLevel(logging.INFO)


def sizeof_fmt(num):
    """Apply size formatting similar to linux sizeof."""
    for unit in ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]:
        if abs(num) < 1024.0:
            return f"{num:.1f} {unit:}"
        num /= 1024.0
    return "Very large"


@blueprint.route("/server_logs")
def index():
    # Create combined profile
    profile_enabled = Config.PROFILE_CODE
    if profile_enabled:
        profiles_dir = Path(Config.PROFILES_FOLDER)
        profile_file = str(Path(Config.PROJECT_ROOT) / "logs" / "profile.txt")
        if profiles_dir.is_dir():
            combined_profile = pstats.Stats()
            for tempfile in profiles_dir.iterdir():
                if tempfile.is_file():
                    combined_profile.add(str(tempfile))
            combined_profile.dump_stats(profile_file)

    txt_logs = [
        logs_folder / f for f in os.listdir(logs_folder) if f.lower().endswith(".txt")
    ]
    txt_logs.sort(key=os.path.getmtime)
    files = []
    for i in sorted(txt_logs, reverse=True):
        stat = Path(logs_folder / i).stat()
        files.append(
            {
                "name": PurePath(i).name,
                "size": stat.st_size,
                "modified": time.strftime(time_fmt, time.localtime(stat.st_mtime)),
            }
        )
    return render_template(
        "server_logs.html",
        hostname=Config.HOSTNAME,
        files=files,
    )


@blueprint.route("/server_logs/<path:file_name>")
def display(file_name):
    """Display the file in the browser."""
    with open(logs_folder / file_name, "r") as f:
        content = f.read()
    return "<pre><b><h2>" + file_name + "</b></h2>" + content + "</pre>"


@blueprint.route("/server_logs/download/<path:file_name>")
def download(file_name):
    """Download the file."""
    log.info("Downloading %s...", logs_folder / file_name)
    return send_file(
        os.path.join(logs_folder, file_name),
        as_attachment=True,
    )
