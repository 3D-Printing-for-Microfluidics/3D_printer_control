"""Control view."""
import json
import logging
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Blueprint, render_template, request, send_from_directory
from markdown2 import markdown

from printer_server.extensions import socketio
from printer_server.settings import Config
from printer_server.threading_wrapper import Thread
import printer_server.views.home
from printer_server.hardware_configuration.hardware_configuration import config_dict
from printer_server.models import PrintQueue
from printer_server.print_file_validator import validate_schema, validate_printer_compatibility

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

conversion_dict = {
    "Focus": "focus",
    "Visitech Focus": "keyence_visitech",
    "Wintech Focus": "keyence_wintech",
    "Tip": "tip",
    "Tilt": "tilt",
    "Rotate": "rotate",
    "Pivot X": "pivot_x",
    "Pivot Y": "pivot_y",
    "Pivot Z": "pivot_z",
    "Wintech X drift": "x_drift",
    "Wintech Y drift": "y_drift",
    "Wintech X Shift per mm Y": "xy_shift",
    "Wintech Y Shift per mm X": "yx_shift",
    "Wintech X Shift per mm X": "xx_shift",
    "Wintech Y Shift per mm Y": "yy_shift",
}

GROUP_NON_ACTIVE_OFFSETS = "Tip/Tilt/Focus Settings"
GROUP_ACTIVE_OFFSETS = "Active Focus Offsets"
GROUP_HEXAPOD_PARAMETERS = "Hexapod Parameters"
GROUP_ALIGNMENT_ADJUSTMENTS = "Alignment Adjustments"
GROUP_IRRADIANCE_TARGETS = "Irradiance Targets"

def register_irradiance_targets():
    if "photodiode" not in config_dict:
        return
    for light_engine in config_dict.get("light_engines", []):
        for wavelength in config_dict.get(light_engine, {}).get("leds_nm", []):
            human = f"{light_engine.capitalize()} {wavelength} nm"
            machine = f"irradiance_target_{light_engine}_{wavelength}"
            conversion_dict.setdefault(human, machine)

position_log_file = str(Path.cwd() / "logs" / "calibration_position_log.txt")
CALIBRATION_PRINTS_ROOT = Path(Config.PRINT_SERVER_FOLDER) / "calibration_prints"

def write_to_position_log(message):
    with open(position_log_file, "a") as f:
        f.write(
            "{} {}\n".format(
                datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), json.dumps(message)
            )
        )


def get_last_calibration_positions_from_logs():
    """Return the last focused position from the position log file.
    """
    log_file = Path(Config.PROJECT_ROOT) / "logs" / "calibration_position_log.txt"
    last_line = None
    try:
        with open(log_file) as f:
            for line in f:
                last_line = line.rstrip()

        last_line = last_line[20:]
        last_line = last_line.replace("'", '"')
        temp = json.loads(last_line)
        return temp
    except FileNotFoundError:
        return {}
    
def human_to_machine(human_string):
    # Normalize the input by replacing underscores with spaces
    normalized = human_string.replace('-', ' ')
    # Convert to machine-readable string
    return conversion_dict.get(normalized)


def resolve_machine_name(value):
    if value in conversion_dict.values():
        return value
    machine = human_to_machine(value)
    if machine is not None:
        return machine
    return value

def machine_to_human(machine_string):
    # Reverse lookup in the dictionary
    for human, machine in conversion_dict.items():
        if machine == machine_string:
            return human
    return None


def _safe_calibration_print_path(relative_path):
    root = CALIBRATION_PRINTS_ROOT.resolve()
    candidate = (CALIBRATION_PRINTS_ROOT / relative_path).resolve()
    if not str(candidate).startswith(str(root)):
        raise ValueError("Invalid calibration print path")
    return candidate


def _rewrite_relative_links(html, base_url):
    def replacer(match):
        attr = match.group(1)
        quote = match.group(2)
        url = match.group(3)
        return f"{attr}={quote}{base_url}/{url}{quote}"

    pattern = r"(src|href)=(['\"])(?![a-zA-Z]+:|/)([^'\"]+)\2"
    return re.sub(pattern, replacer, html)


def _render_readme(readme_path, folder_rel):
    raw = readme_path.read_text(encoding="utf-8")
    html = markdown(raw, extras=["fenced-code-blocks", "tables"])
    base_url = f"/calibration_prints/{folder_rel}"
    return _rewrite_relative_links(html, base_url)


def list_calibration_prints():
    prints = []
    if not CALIBRATION_PRINTS_ROOT.exists():
        return prints
    allowed = config_dict.get("calibration_prints")
    allowed_set = None
    if isinstance(allowed, list):
        allowed_set = {name.strip() for name in allowed if isinstance(name, str)}
    for subdir in sorted(CALIBRATION_PRINTS_ROOT.iterdir()):
        if not subdir.is_dir():
            continue
        if allowed_set is not None and subdir.name not in allowed_set:
            continue
        json_files = sorted(subdir.glob("*.json"))
        if not json_files:
            continue
        json_file = json_files[0]
        rel = json_file.relative_to(CALIBRATION_PRINTS_ROOT).as_posix()
        prints.append({"id": rel, "name": subdir.name})
    return prints


def get_calibration_print_details(print_id):
    print_path = _safe_calibration_print_path(print_id)
    if not print_path.exists() or print_path.suffix.lower() != ".json":
        raise ValueError("Calibration print not found")
    print_settings = json.loads(print_path.read_text(encoding="utf-8"))
    variables = print_settings.get("Variables", {})
    translation = variables.get("Comment", {})
    if isinstance(translation, str):
        try:
            translation = json.loads(translation)
        except json.JSONDecodeError:
            translation = {}
    if not isinstance(translation, dict):
        translation = {}
    variable_items = []
    for key, value in variables.items():
        if key == "Comment":
            continue
        variable_items.append(
            {"key": key, "label": translation.get(key, key), "value": value}
        )
    header = print_settings.get("Header", {})
    readme_html = ""
    readme_path = print_path.parent / "README.md"
    if readme_path.exists():
        folder_rel = print_path.parent.relative_to(CALIBRATION_PRINTS_ROOT).as_posix()
        readme_html = _render_readme(readme_path, folder_rel)
    return {
        "id": print_id,
        "name": print_path.parent.name,
        "variables": variable_items,
        "readme_html": readme_html,
    }


def _coerce_variable_value(raw_value, original_value):
    if raw_value is None or str(raw_value).strip() == "":
        return original_value
    if isinstance(original_value, bool):
        val = str(raw_value).strip().lower()
        if val in {"true", "1", "yes", "on"}:
            return True
        if val in {"false", "0", "no", "off"}:
            return False
        return original_value
    if isinstance(original_value, int) and not isinstance(original_value, bool):
        try:
            return int(raw_value)
        except (ValueError, TypeError):
            try:
                return int(float(raw_value))
            except (ValueError, TypeError):
                return original_value
    if isinstance(original_value, float):
        try:
            return float(raw_value)
        except (ValueError, TypeError):
            return original_value
    try:
        return json.loads(raw_value)
    except (ValueError, TypeError):
        return raw_value


def _sanitize_filename_part(value):
    text = str(value)
    text = text.replace("/", "-").replace("\\", "-")
    text = re.sub(r"[^A-Za-z0-9 _.,:()\-]", "", text)
    return text.strip()


def _format_calibration_vars_for_filename(variables):
    items = []
    for key in sorted(variables.keys()):
        if key == "Comment":
            continue
        items.append(f"{_sanitize_filename_part(key)}:{_sanitize_filename_part(variables[key])}")
    if not items:
        return ""
    joined = ", ".join(items)
    if len(joined) > 120:
        joined = joined[:117] + "..."
    return f" ({joined})"

# Create bluprint
blueprint = Blueprint(
    "calibration",
    __name__,
    url_prefix="/",
    template_folder="../drivers",
    static_folder="../drivers",
)


@blueprint.route("/calibration_prints/<path:filename>")
def calibration_prints_file(filename):
    return send_from_directory(CALIBRATION_PRINTS_ROOT, filename)

def create_calibration_data():
    calibration_data = []

    def add_to_list(settings, group):
        for setting in settings:
            calibration_data.append(
                {
                    "machine_name": setting,
                    "human_name": machine_to_human(setting),
                    "group": group,
                    "value": last_positions.get(setting, 0.0),
                }
            )

    register_irradiance_targets()
    last_positions = get_last_calibration_positions_from_logs()
    # Use dynamic focus if available
    if "keyence" in config_dict.keys():
        keyence_sensors = []
        for sensor in config_dict["keyence"]["sensors"].keys():
            setting = f"keyence_{sensor}"
            if setting not in conversion_dict.values():
                conversion_dict[f"{sensor.capitalize()} Focus"] = setting
            keyence_sensors.append(setting)
        add_to_list(keyence_sensors, GROUP_ACTIVE_OFFSETS)
    else:
        add_to_list(["focus"], GROUP_NON_ACTIVE_OFFSETS)

    # Add TTR axis (if hexapod also add pivot)
    if "hexapod" in config_dict.keys():
        add_to_list(["tip", "tilt"], GROUP_NON_ACTIVE_OFFSETS)
        add_to_list(["rotate", "pivot_x", "pivot_y", "pivot_z"], GROUP_HEXAPOD_PARAMETERS)
    else:
        add_to_list(["tip", "tilt"], GROUP_NON_ACTIVE_OFFSETS)
    
    # Add wintech correction
    if "wintech" in config_dict.keys():
        add_to_list(
            ["x_drift", "y_drift", "xy_shift", "yx_shift", "xx_shift", "yy_shift"],
            GROUP_ALIGNMENT_ADJUSTMENTS,
        )

    if "photodiode" in config_dict:
        for light_engine in config_dict.get("light_engines", []):
            for wavelength in config_dict.get(light_engine, {}).get("leds_nm", []):
                add_to_list(
                    [f"irradiance_target_{light_engine}_{wavelength}"],
                    GROUP_IRRADIANCE_TARGETS,
                )

    return calibration_data


# Decorator to handle navigation to calibration page
@blueprint.route("/calibration")
def index():
    initialized = printer_server.views.home.print_control.state != "uninitialized"

    return render_template(
        "calibration.html",
        initialized=initialized,
        hostname=Config.HOSTNAME,
        calibration_data=create_calibration_data(),
    )


@socketio.on("calibration_prints_list", namespace="/calibration")
def calibration_prints_list():
    socketio.emit(
        "calibration_prints_list_done",
        {"prints": list_calibration_prints()},
        namespace="/calibration",
    )


@socketio.on("calibration_prints_details", namespace="/calibration")
def calibration_prints_details(message):
    try:
        print_id = (message or {}).get("id")
        details = get_calibration_print_details(print_id)
        socketio.emit(
            "calibration_prints_details_done", details, namespace="/calibration"
        )
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as ex:
        socketio.emit(
            "calibration_prints_flash",
            {"category": "warning", "text": str(ex)},
            namespace="/calibration",
        )


@socketio.on("calibration_prints_add_to_queue", namespace="/calibration")
def calibration_prints_add_to_queue(message):
    try:
        payload = message or {}
        print_id = payload.get("id")
        override_vars = payload.get("variables", {})
        print_path = _safe_calibration_print_path(print_id)
        if not print_path.exists() or print_path.suffix.lower() != ".json":
            raise ValueError("Calibration print not found")

        print_settings = json.loads(print_path.read_text(encoding="utf-8"))
        variables = print_settings.get("Variables", {})
        for key, value in override_vars.items():
            if key in variables and key != "Comment":
                variables[key] = _coerce_variable_value(value, variables.get(key))
        print_settings["Variables"] = variables

        upload_time = datetime.now()
        zip_path = (
            Path(Config.UPLOAD_FOLDER)
            / "queue"
            / f"{upload_time.strftime('job-%Y-%m-%d_%H-%M-%S.%f')}.zip"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            for item in print_path.parent.iterdir():
                if item.is_file():
                    if item.suffix.lower() == ".json" and item.name != print_path.name:
                        continue
                    shutil.copy2(item, temp_root / item.name)
                elif item.is_dir():
                    shutil.copytree(item, temp_root / item.name)

            (temp_root / print_path.name).write_text(
                json.dumps(print_settings, indent=4), encoding="utf-8"
            )

            base_name = str(zip_path)[: -len(".zip")]
            shutil.make_archive(base_name, "zip", temp_root)

        print_settings, schema_ver = validate_schema(zip_path)
        if schema_ver not in config_dict["valid_schema_versions"]:
            raise ValueError(f"Printer does not support {schema_ver} JSON format")
        validate_printer_compatibility(print_settings)

        params_suffix = _format_calibration_vars_for_filename(variables)
        display_name = f"{print_path.parent.name}{params_suffix}.zip"
        print_job = PrintQueue(
            original_filename=display_name,
            upload_time=upload_time,
            upload_ip=request.remote_addr,
        ).save()

        socketio.emit(
            "job uploaded",
            {
                "id": print_job.id,
                "name": display_name,
                "upload_time": upload_time.strftime("%Y-%m-%d %H:%M:%S"),
                "upload_ip": request.remote_addr,
            },
            namespace="/printing",
        )
        socketio.emit(
            "calibration_prints_add_done",
            {"text": f"{display_name} added to queue."},
            namespace="/calibration",
        )
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as ex:
        if "zip_path" in locals() and Path(zip_path).exists():
            Path(zip_path).unlink(missing_ok=True)
        socketio.emit(
            "calibration_prints_flash",
            {"category": "warning", "text": str(ex)},
            namespace="/calibration",
        )

@socketio.on("set", namespace="/calibration")
def set(message):
    register_irradiance_targets()
    mode = message["mode"]
    distance = float(message["distance"])
    parameter = message.get("parameter", None)
    group = message.get("group", None)
    last_positions = get_last_calibration_positions_from_logs()
    machine_name = resolve_machine_name(parameter)
    round_precision = 1
    if group == GROUP_IRRADIANCE_TARGETS:
        round_precision = 2
    if mode == "absolute":
        last_positions[machine_name] = round(distance, round_precision)
    elif mode == "relative":
        last_positions[machine_name] = round(
            distance + last_positions.get(machine_name, 0.0), round_precision
        )
    write_to_position_log(last_positions)
    socketio.emit(
        "set_done", create_calibration_data(), namespace="/calibration"
    )

@socketio.on("goto", namespace="/calibration")
def goto():
    from printer_server.hardware_configuration.hardware_configuration import driver_handles
    calibration_positions = get_last_calibration_positions_from_logs()

    focus = calibration_positions.get("focus",0)
    tip = calibration_positions.get("tip",0)
    tilt = calibration_positions.get("tilt",0)
    rotate = calibration_positions.get("rotate",0)
    pivot_x = calibration_positions.get("pivot_x",0)
    pivot_y = calibration_positions.get("pivot_y",0)
    pivot_z = calibration_positions.get("pivot_z",0)

    focus /= 1000
    tip /= 1000
    tilt /= 1000
    rotate /= 1000


    # set hexapod pivot
    if "hexapod" in config_dict.keys():
        # move tt to 0
        driver_handles.ttr_stage.threadedTTRMove(log, 0, 0, 0)

        x = pivot_x/1000
        y = pivot_y/1000
        z = pivot_z/1000
        driver_handles.hexapod.set_pivot_point(x,y,z)

    # move ttr
    ttr_threads = driver_handles.ttr_stage.threadedTTRMove(log, tip, tilt, rotate, join=False)

    # move focus (if not dynamic)
    focus_thread = driver_handles.focus_stage.threadedFocusMove(log, focus, join=False)

    for thread in ttr_threads:
        if thread is not None:
            thread.join()
            if thread.exception is not None:
                raise thread.exception
    focus_thread.join()
    if focus_thread.exception is not None:
        raise focus_thread.exception

    socketio.emit(
        "goto_done", create_calibration_data(), namespace="/calibration"
    )
