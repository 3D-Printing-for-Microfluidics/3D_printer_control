import json
from pathlib import Path
import logging
import signal
from flask import Blueprint, request, render_template
from flask_socketio import join_room, leave_room

from printer_server.settings import Config
from printer_server.models import PrintQueue
from printer_server.extensions import socketio

# Dynamically get hardware components
configuration_path = Path(Config.PRINT_SERVER_FOLDER).rglob("hardware_configuration.json")
with open(next(configuration_path), "r") as file_handle:
    config_dict = json.load(file_handle)
config_dict = config_dict[Config.HOSTNAME]

blueprint = Blueprint("home", __name__, url_prefix="/", static_folder="../static")
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

shutdown_handle = None

# Dynamically import PrintControl
if Config.HOSTNAME == "HR3v3test":
    from printer_server.printer_control.print_control_subclasses import (
        HR3v3u_PrintControl,
    )

    print_control = HR3v3_PrintControl()
elif Config.HOSTNAME == "HR3v3":
    from printer_server.printer_control.print_control_subclasses import HR3v3_PrintControl

    print_control = HR3v3_PrintControl()
elif Config.HOSTNAME == "HR3v3u":
    from printer_server.printer_control.print_control_subclasses import (
        HR3v3u_PrintControl,
    )

    print_control = HR3v3u_PrintControl()
elif Config.HOSTNAME == "HR4":
    from printer_server.printer_control.print_control_subclasses import (
        HR4Film_PrintControl,
    )

    print_control = HR4Film_PrintControl()
elif Config.HOSTNAME == "MR1v1":
    from printer_server.printer_control.print_control_subclasses import MR1v1_PrintControl

    print_control = MR1v1_PrintControl()
else:
    log.error("Printer control module not found")


@blueprint.route("/")
def index():
    allJobs = PrintQueue.query.all()

    global shutdown_handle
    shutdown_handle = request.environ.get("werkzeug.server.shutdown")
    if shutdown_handle is None:
        raise RuntimeError("Not running with the Werkzeug Server")

    if "loadcell" in config_dict.keys():
        return render_template(
            "home.html",
            allJobs=allJobs,
            hostname=Config.HOSTNAME,
            graph_autoscale=print_control.loadcell.graph_autoscale,
        )
    else:
        return render_template(
            "home.html",
            allJobs=allJobs,
            hostname=Config.HOSTNAME
        )

def update_printer_state(state, msg):
    socketio.emit(state, msg, namespace="/printing", broadcast=True)

if "loadcell" in config_dict.keys():
    def clear_loadcell_graph():
        socketio.emit("loadcell_graph_clear", namespace="/printing")


    def update_loadcell_graph(msg):
        socketio.emit("loadcell_graph_data", msg, namespace="/printing", room="loadcell")


def send_bootstrap_alert(msg):
    socketio.emit(
        "bootstrap alert",
        {"text": msg, "category": "warning"},
        namespace="/printing",
    )


@socketio.on("connect", namespace="/printing")
def connect():
    socketio.emit(
        print_control.state,
        dict(),
        namespace="/printing",
        broadcast=False,
        room=request.sid,
    )


@socketio.on("disconnect", namespace="/printing")
def disconnect():
    log.debug("Socket disconnected %s", request.sid)


@socketio.on("initialize", namespace="/printing")
# pylint: disable=unused-argument
def initialize(message):
    print_control.initialize(run_in_thread=False, top_level=True)


@socketio.on("planarization step 1", namespace="/printing")
# pylint: disable=unused-argument
def planarization_step_1(message):
    print_control.planarization_step_1()


@socketio.on("planarization step 2", namespace="/printing")
# pylint: disable=unused-argument
def planarization_step_2(message):
    print_control.planarization_step_2()


@socketio.on("start", namespace="/printing")
# pylint: disable=unused-argument
def start_print(message):
    print_control.start(message["job"])


@socketio.on("pause", namespace="/printing")
# pylint: disable=unused-argument
def pause_print(message):
    print_control.pause()


@socketio.on("resume", namespace="/printing")
# pylint: disable=unused-argument
def resume_print(message):
    print_control.resume()


@socketio.on("stop", namespace="/printing")
# pylint: disable=unused-argument
def stop(message):
    print_control.stop()


@socketio.on("shutdown", namespace="/printing")
# pylint: disable=unused-argument
def shutdown(message):
    is_critical = False
    if message == "critical":
        is_critical = True
    print_control.shutdown(is_critical)
    

def shutdown_exception(exception, trace):
    shutdown("critical")
signal.signal(signal.SIGINT, shutdown_exception)

if "loadcell" in config_dict.keys():
    @socketio.on("request_loadcell_data", namespace="/printing")
    def join_loadcell_room():
        join_room("loadcell")


    @socketio.on("unrequest_loadcell_data", namespace="/printing")
    def leave_loadcell_room():
        leave_room("loadcell")


@blueprint.route("handle-upload", methods=["POST"])
def handle_upload():
    print_control.handle_upload(request)
    return ""


@socketio.on("delete job", namespace="/printing")
def delete_job(message, delete_on_disk=True):
    print_control.delete_job(message, delete_on_disk=True)
