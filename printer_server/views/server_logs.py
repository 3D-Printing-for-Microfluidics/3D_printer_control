import logging
from flask import Blueprint, render_template


blueprint = Blueprint("server_logs", __name__, url_prefix="/", static_folder="../static")
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


@blueprint.route("/server_logs")
def index():
    return render_template("server_logs.html")
