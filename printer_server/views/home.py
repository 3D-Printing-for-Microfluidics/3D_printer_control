import logging
from flask import Blueprint, request, render_template
from flask_socketio import join_room, leave_room

from printer_server.settings import Config
from printer_server.models import PrintQueue
from printer_server.extensions import socketio

blueprint = Blueprint("home", __name__, url_prefix="/", static_folder="../static")
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

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
    return render_template(
        "home.html",
        allJobs=allJobs,
        hostname=Config.HOSTNAME,
        graph_autoscale=print_control.loadcell.graph_autoscale,
    )


def update_printer_state(state, msg):
    socketio.emit(state, msg, namespace="/printing", broadcast=True)


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
    print_control.shutdown()


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
