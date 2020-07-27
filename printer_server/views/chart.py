from math import sin, pi
import random
import time
from flask import Blueprint, render_template

from printer_server.extensions import socketio

blueprint = Blueprint("chart", __name__, url_prefix="/", static_folder="../static")


@blueprint.route("/chart")
def index():
    return render_template("chart.html")


# @socketio.on("connect", namespace="/chart")
# def connect():
#     print("you connected!")
#     for _ in range(60):
#         msg = {"data": random.randint(0, 10)}
#         print("new_data", msg)
#         socketio.emit("new_data", msg, namespace="/chart")
#         time.sleep(1)


@socketio.on("graph_ready", namespace="/chart")
def test():
    # f = 200 / 8000
    # sample = 2000
    # a = [0] * sample
    # for n in range(sample):
    #     a[n] = 30 * sin(2 * pi * f * n) + 40

    # print("got message from frontend")
    # time.sleep(1)  # MIN ~0.3
    msg = {"x1": random.randint(0, 30), "x2": random.randint(30, 50)}
    socketio.emit("graph_data", msg, namespace="/chart")
