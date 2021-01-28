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

@socketio.on("set_loadcell_source", namespace="/loadcell")
def set_loadcell_source(message):
    """set_loadcell_source -- Sets the variable determining if loadcell is using battery source"""
    hardware_driver_handles.loadcell.set_loadcell_source(message == "Battery")


@socketio.on("get_loadcell_source", namespace="/loadcell")
def get_loadcell_source():
    """Return the loadcell source flag."""
    socketio.emit(
        "loadcell_source",
        hardware_driver_handles.loadcell.get_loadcell_source(),
        namespace="/loadcell",
        broadcast=True,
    )


@socketio.on("graph_start", namespace="/loadcell")
def test():
    global running
    if not running:
        running = True
        while running:
            data = hardware_driver_handles.loadcell.get_current_data()
            
            msg = {"data": data}
            socketio.emit("graph_data", msg, namespace="/loadcell")
            time.sleep(.05)
