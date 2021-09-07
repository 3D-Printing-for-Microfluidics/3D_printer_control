import time
import threading
from flask import Blueprint, render_template

from printer_server.settings import Config
from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles

blueprint = Blueprint("loadcell", __name__, url_prefix="/", static_folder="../static")
running = False
thread = None


@blueprint.route("/loadcell")
def index():
    return render_template("loadcell.html", hostname=Config.HOSTNAME)


def loop():
    global running
    if not running:
        running = True
        while running:
            data = driver_handles.loadcell.get_current_data()

            msg = {"data": data}
            socketio.emit("graph_data", msg, namespace="/loadcell")
            time.sleep(0.025)


@socketio.on("loadcell_graph_start", namespace="/loadcell")
def loadcell_graph_start():
    global thread
    if thread is None:
        thread = threading.Thread(target=loop)
        thread.run()


@socketio.on("loadcell_graph_stop", namespace="/loadcell")
def loadcell_graph_stop():
    global running
    running = False
