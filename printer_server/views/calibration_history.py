import os
import shutil
import logging
from flask_socketio import emit
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, jsonify, flash, send_file


from printer_server.settings import Config
from printer_server.extensions import socketio, db
from printer_server.views.table import *
from printer_server.views.calibration import create_calibration_data, GROUP_ACTIVE_OFFSETS, GROUP_NON_ACTIVE_OFFSETS
from printer_server.forms import StartSessionForm, RegisterForm, EndSessionForm
from printer_server.models import PrintRecord, PrintQueue, Session, User, Calibration
from printer_server.hardware_configuration.hardware_configuration import config_dict
from printer_server.print_file_validator import validate_schema, validate_printer_compatibility

blueprint = Blueprint(
    "calibration_history", __name__, url_prefix="/", static_folder="../static"
)
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def generate_calibration_table_column_definition():
    all_keys = set()
    for cal in Calibration.query:
        all_keys.update(cal.calibration_data.keys())

    calibration_data = create_calibration_data()

    # create lut
    lut = {}
    for data in calibration_data:
        lut[data["machine_name"]] = {
            "group": data["group"],
            "full_name": data["group"] + " - " + ((data["subgroup"] + " - ") if data["subgroup"] else "") + data["human_name"],
        }

    columns = [
        Column(key="col-calibration-date", name="Calibration Date", value=lambda r: r.calibration_date, type="datetime", visible=True, db_col=Calibration.calibration_date, db_filter=generate_datetime_lambda(Calibration.calibration_date)),
    ]
    for key in all_keys:
        if key in lut:
            human_name = lut[key]["full_name"]

            db_col = db.func.json_extract(
                Calibration.calibration_data,
                f'$.{key}'
            ).label(key)

            columns.append(Column(
                key=f"col-{key}",
                name=human_name,
                value=lambda r, k=key: r.calibration_data.get(k),
                visible=lut[key]["group"] in [GROUP_ACTIVE_OFFSETS, GROUP_NON_ACTIVE_OFFSETS],
                db_col=db_col,
                db_filter=generate_string_lambda(db_col),
            ))

    def get_sort_col(column_key):
        map = {}
        for col in columns:
            if col.db_col is not None:
                map[col.key] = col.db_col
        return map.get(column_key, Calibration.calibration_date)
    
    def get_filter_lambda(column_key):
        map = {}
        for col in columns:
            if col.db_filter is not None:
                map[col.key] = col.db_filter
        return map.get(column_key, lambda x: None)

    return {
        "columns": columns,
        "sort_columns": get_sort_col,
        "filter_lambdas": get_filter_lambda,
    }



@blueprint.route("/calibration_history")
def index():
    return render_template(
        "calibration_history.html",
        hostname=Config.HOSTNAME,
    )


@blueprint.route("/calibration_history/calibration_table")
def print_table():
    subtable_id = request.args.get("session_id", None)
    if subtable_id is None:
        table = generate_table(
            name = "Calibrations",
            table_key = "calibration-table", 
            route = "/calibration_history/calibration_table",
            query = Calibration.query, 
            table_definition = generate_calibration_table_column_definition(),  
            has_filters = True,
            subtables = None,
            paginate = 20, 
            args = request.args
        )
    else:
        table = generate_table(
            name = "Calibration",
            table_key = f"session-history-Calibration-subtable-{subtable_id}",
            route = f"/calibration_history/calibration_table?session_id={subtable_id}",
            # query for the calibration data for the specific session
            query = Calibration.query.join(Session).filter(Session.id == subtable_id),
            table_definition = generate_calibration_table_column_definition(),
            has_filters = False,
            subtables = None,
            paginate = -1, 
            args = request.args
        )
    
    return render_template(
        "partials/table.html",
        table=table
    )