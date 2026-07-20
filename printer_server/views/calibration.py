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
import printer_server.views.home as home
from printer_server.hardware_configuration.hardware_configuration import config_dict
from printer_server.models import PrintQueue, Session, Calibration
from printer_server.print_file_validator import validate_schema, validate_printer_compatibility
from printer_server.views.users import require_permissions, socket_require_permissions

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

CALIBRATION_PRINTS_ROOT = Path(Config.PRINT_SERVER_FOLDER) / "calibration_prints"

# Create bluprint
blueprint = Blueprint(
    "calibration",
    __name__,
    url_prefix="/",
    template_folder="../drivers",
    static_folder="../drivers",
)

conversion_dict = {
    "focus": "Focus",
    "tip": "Tip",
    "tilt": "Tilt",
    "rotate": "Rotate",
    "pivot_x": "Pivot X",
    "pivot_y": "Pivot Y",
    "pivot_z": "Pivot Z",
}

GROUP_NON_ACTIVE_OFFSETS = "Tip/Tilt/Focus Settings"
GROUP_ACTIVE_OFFSETS = "Active Focus Offsets"
GROUP_HEXAPOD_PARAMETERS = "Hexapod Parameters"
GROUP_ALIGNMENT_ADJUSTMENTS = "Alignment Adjustments"
GROUP_STITCHING_ADJUSTMENTS = "Stitching Adjustments"
GROUP_IRRADIANCE_TARGETS = "Irradiance Targets"

def register_irradiance_targets():
    if "photodiode" not in config_dict:
        return
    for light_engine in config_dict.get("light_engines", []):
        for wavelength in config_dict.get(light_engine, {}).get("leds_nm", []):
            human = f"{light_engine.capitalize()} {wavelength} nm"
            machine = f"irradiance_target_{light_engine}_{wavelength}"
            conversion_dict.setdefault(machine, human)


def register_active_tt():
    for light_engine in config_dict.get("light_engines", []):
        for axis in ["tip", "tilt"]:
            human = f"{light_engine.capitalize()} {axis.capitalize()}"
            machine = f"{light_engine}_{axis}_base"
            conversion_dict.setdefault(machine, human)

            human_offset = f"{light_engine.capitalize()} {axis.capitalize()} Offset"
            machine_offset = f"{light_engine}_{axis}_offset"
            conversion_dict.setdefault(machine_offset, human_offset)


def register_active_focus():
    for light_engine in config_dict.get("light_engines", []):
        human = f"{light_engine.capitalize()} Focus"
        machine = f"{light_engine}_focus_base"
        conversion_dict.setdefault(machine, human)

        human_offset = f"{light_engine.capitalize()} Focus Offset"
        machine_offset = f"{light_engine}_focus_offset"
        conversion_dict.setdefault(machine_offset, human_offset)


def register_light_engine_alignment():
    for light_engine in config_dict.get("light_engines", []):
        for axis in ["x", "y"]:
            # human = f"{light_engine.capitalize()} {axis.upper()} Alignment"
            human = axis.upper()
            machine = f"{light_engine}_{axis}_alignment"
            conversion_dict.setdefault(machine, human)


def register_stitching_correction():
    for light_engine in config_dict.get("light_engines", []):
        for axis in ["x", "y"]:
            for correction in ["x", "y", "focus"]:
                # human = f"{light_engine.capitalize()} {correction.capitalize()} um per mm {axis.upper()}"
                human = correction.capitalize()
                machine = f"{light_engine}_{correction}_shift_{axis}"
                conversion_dict.setdefault(machine, human)


def get_last_calibration_positions_from_logs():
    # Get the last calibration positions from the database
    from autoapp import app
    with app.app_context():
        return Calibration.get_last_positions()


def create_calibration_data():
    from printer_server.hardware_configuration.hardware_configuration import (
        driver_handles,
    )
    calibration_data = []

    def add_to_list(settings, group, subgroup=None):
        for setting in settings:
            calibration_data.append(
                {
                    "machine_name": setting,
                    "human_name": conversion_dict.get(setting),
                    "group": group,
                    "subgroup": subgroup,
                    "value": last_positions.get(setting, 0.0),
                }
            )

    register_irradiance_targets()
    register_active_focus()
    register_active_tt()
    register_light_engine_alignment()
    register_stitching_correction()

    last_positions = get_last_calibration_positions_from_logs()
    if "photodiode" in config_dict:
        for light_engine in config_dict.get("light_engines", []):
            for wavelength in config_dict.get(light_engine, {}).get("leds_nm", []):
                add_to_list(
                    [f"irradiance_target_{light_engine}_{wavelength}"],
                    GROUP_IRRADIANCE_TARGETS,
                )
    auto_tip_tilt = driver_handles.ttr_stage.config_dict.get("auto_tip_tilt", False)
    if auto_tip_tilt:
        settings_list = []
        for le in config_dict["light_engines"]:
            for axis in ["tip", "tilt"]:
                # settings_list.append(f"{le}_{axis}_base") # Don't show on Calibration page
                settings_list.append(f"{le}_{axis}_offset")
        add_to_list(settings_list, GROUP_ACTIVE_OFFSETS)

    auto_focus = ("keyence" in config_dict and config_dict["keyence"].get("auto_focus_with_keyence"))
    if auto_focus:
        settings_list = []
        for le in config_dict["light_engines"]:
            # settings_list.append(f"{le}_focus_base") # Don't show on Calibration page
            settings_list.append(f"{le}_focus_offset")
        add_to_list(settings_list, GROUP_ACTIVE_OFFSETS)

    if not auto_tip_tilt:
        add_to_list(["tip", "tilt"], GROUP_NON_ACTIVE_OFFSETS)

    if not auto_focus:
        add_to_list(["focus"], GROUP_NON_ACTIVE_OFFSETS)

    # Add TTR axis (if hexapod also add pivot)
    if "hexapod" in config_dict.keys():
        add_to_list(["rotate", "pivot_x", "pivot_y", "pivot_z"], GROUP_HEXAPOD_PARAMETERS)
    
    if "coord_systems" in config_dict.keys():
        for light_engine in config_dict.get("light_engines", []):
            # Add light engine alignment (if xy stages present)
            add_to_list(
                [f"{light_engine}_x_alignment", f"{light_engine}_y_alignment"],
                GROUP_ALIGNMENT_ADJUSTMENTS,
                subgroup=light_engine.capitalize(),
            )
    
            # Add stitching correction (if xy stages present)
            for axis in ["x", "y"]:
                _list = [
                    f"{light_engine}_x_shift_{axis}",
                    f"{light_engine}_y_shift_{axis}"
                ]
                keyence_dict = config_dict.get("keyence", {})
                if not(keyence_dict.get("auto_focus_with_keyence", False) and keyence_dict.get("direct_focal_measurement", False)):
                    _list.append(f"{light_engine}_focus_shift_{axis}")
                add_to_list(
                    _list,
                    GROUP_STITCHING_ADJUSTMENTS,
                    subgroup=f"{light_engine.capitalize()} (per mm {axis.upper()})",
                )

    return calibration_data


# Decorator to handle navigation to calibration page
@blueprint.route("/calibration")
@require_permissions(permission="calibration", require_session=True)
def index():
    initialized = home.print_control.state != "uninitialized"

    return render_template(
        "calibration.html",
        initialized=initialized,
        hostname=Config.HOSTNAME,
        calibration_data=create_calibration_data(),
    )


def write_to_position_log(message):
    position_log_file = str(Path.cwd() / "logs" / "calibration_position_log.txt")
    with open(position_log_file, "a") as f:
        f.write(
            "{} {}\n".format(
                datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), json.dumps(message)
            )
        )

    from autoapp import app
    with app.app_context():
        calibration = Calibration(
            calibration_date=datetime.now(),
            calibration_data=message
        )
        calibration.save()


@socketio.on("set", namespace="/calibration")
@socket_require_permissions(permission="calibration", require_session=True)
def set(message):
    register_irradiance_targets()
    mode = message["mode"]
    distance = float(message["distance"])
    parameter = message.get("parameter", None)
    group = message.get("group", None)
    last_positions = get_last_calibration_positions_from_logs()
    machine_name = parameter
    round_precision = 1
    if group == GROUP_IRRADIANCE_TARGETS:
        round_precision = 2
    if mode == "absolute":
        last_positions[machine_name] = round(distance, round_precision)
    elif mode == "relative":
        last_positions[machine_name] = round(
            distance + last_positions.get(machine_name, 0.0), round_precision
        )

    cal_data = create_calibration_data()
    for val in cal_data:
        if val["machine_name"] not in last_positions:
            last_positions[val["machine_name"]] = 0.0

    write_to_position_log(last_positions)
    socketio.emit("set_done", create_calibration_data(), namespace="/calibration")


@socketio.on("goto", namespace="/calibration")
@socket_require_permissions(permission="calibration", require_session=True)
def goto():
    from printer_server.hardware_configuration.hardware_configuration import (
        driver_handles,
    )

    calibration_positions = get_last_calibration_positions_from_logs()

    focus = calibration_positions.get("focus", 0)
    tip = calibration_positions.get("tip", 0)
    tilt = calibration_positions.get("tilt", 0)
    rotate = calibration_positions.get("rotate", 0)
    pivot_x = calibration_positions.get("pivot_x", 0)
    pivot_y = calibration_positions.get("pivot_y", 0)
    pivot_z = calibration_positions.get("pivot_z", 0)

    focus /= 1000
    tip /= 1000
    tilt /= 1000
    rotate /= 1000

    # set hexapod pivot
    if "hexapod" in config_dict.keys():
        # move tt to 0
        driver_handles.ttr_stage.threadedTTRMove(log, 0, 0, 0)

        x = pivot_x / 1000
        y = pivot_y / 1000
        z = pivot_z / 1000
        driver_handles.hexapod.set_pivot_point(x, y, z)

    # move ttr
    ttr_threads = driver_handles.ttr_stage.threadedTTRMove(
        log, tip, tilt, rotate, join=False
    )

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

    socketio.emit("goto_done", create_calibration_data(), namespace="/calibration")


@blueprint.route("/calibration_prints/<path:filename>")
@require_permissions(permission="calibration", require_session=True)
def calibration_prints_file(filename):
    return send_from_directory(CALIBRATION_PRINTS_ROOT, filename)


def _latest_mtime_in_dir(root_dir):
    latest = root_dir.stat().st_mtime
    for path in root_dir.rglob("*"):
        try:
            latest = max(latest, path.stat().st_mtime)
        except FileNotFoundError:
            continue
    return latest


def extract_calibration_print_archives():
    if not CALIBRATION_PRINTS_ROOT.exists():
        return
    allowed = config_dict.get("calibration_prints")
    allowed_set = None
    if isinstance(allowed, list):
        allowed_set = {name.strip() for name in allowed if isinstance(name, str)}
    for zip_path in sorted(CALIBRATION_PRINTS_ROOT.glob("*.zip")):
        if not zip_path.is_file():
            continue
        if allowed_set is not None and zip_path.stem not in allowed_set:
            continue
        target_dir = CALIBRATION_PRINTS_ROOT / zip_path.stem
        try:
            zip_mtime = zip_path.stat().st_mtime
        except FileNotFoundError:
            continue

        if target_dir.exists() and target_dir.is_dir():
            try:
                latest_mtime = _latest_mtime_in_dir(target_dir)
            except FileNotFoundError:
                latest_mtime = 0
            if zip_mtime <= latest_mtime:
                continue
            shutil.rmtree(target_dir, ignore_errors=True)

        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.unpack_archive(str(zip_path), str(target_dir))
            log.info("Extracted calibration print archive: %s", zip_path.name)
        except (shutil.ReadError, ValueError) as ex:
            log.warning("Failed to extract %s: %s", zip_path.name, ex)
            shutil.rmtree(target_dir, ignore_errors=True)



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


@socketio.on("calibration_prints_list", namespace="/calibration")
@socket_require_permissions(permission="calibration", require_session=True)
def calibration_prints_list():
    socketio.emit(
        "calibration_prints_list_done",
        {"prints": list_calibration_prints()},
        namespace="/calibration",
    )


@socketio.on("calibration_prints_details", namespace="/calibration")
@socket_require_permissions(permission="calibration", require_session=True)
def calibration_prints_details(message):
    try:
        print_id = (message or {}).get("id")
        details = get_calibration_print_details(print_id)
        socketio.emit(
            "calibration_prints_details_done", details, namespace="/calibration"
        )
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as ex:
        log.warning("Error retrieving calibration print details: %s", ex)
        socketio.emit(
            "calibration_prints_add_done",
            namespace="/calibration",
        )


@socketio.on("calibration_prints_add_to_queue", namespace="/calibration")
@socket_require_permissions(permission="calibration", require_session=True)
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
            user=Session.get_session_user()
        ).save()

        socketio.emit(
            "job uploaded",
            {
                "id": print_job.id,
                "name": display_name,
                "upload_time": upload_time.strftime("%Y-%m-%d %H:%M:%S"),
                "upload_ip": request.remote_addr,
                "user_name": Session.get_session_user().full_name if Session.get_session_user() else None,
                "is_current_user": True
            },
            namespace="/printing",
        )
        home.send_bootstrap_alert(f"Calibration print {display_name} added to queue.", level="success")
        socketio.emit(
            "calibration_prints_add_done",
            namespace="/calibration",
        )
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as ex:
        if "zip_path" in locals() and Path(zip_path).exists():
            Path(zip_path).unlink(missing_ok=True)
        log.warning("Error adding calibration print to queue: %s", ex)
        socketio.emit(
            "calibration_prints_add_done",
            namespace="/calibration",
        )