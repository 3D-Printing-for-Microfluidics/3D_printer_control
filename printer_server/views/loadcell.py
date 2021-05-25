from math import sin, pi
import random
import time
import datetime
from flask import Blueprint, render_template

from printer_server.extensions import socketio
from printer_server.hardware_configuration import hardware_driver_handles

blueprint = Blueprint("loadcell", __name__, url_prefix="/", static_folder="../static")
running = False

@blueprint.route("/loadcell")
def index():
    return render_template("loadcell.html")


@socketio.on("graph_start", namespace="/loadcell")
def test():
    global running
    if not running:
        running = True
        while running:
            data = hardware_driver_handles.loadcell.get_current_data()
            
            msg = {"data": data}
            socketio.emit("graph_data", msg, namespace="/loadcell")
            time.sleep(.025)
