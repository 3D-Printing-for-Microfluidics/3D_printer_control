import logging
from datetime import datetime
from flask_socketio import emit
from flask import Blueprint, request, render_template, jsonify

from printer_server.extensions import socketio
from printer_server.models import Session, User, Calibration
from printer_server.forms import StartSessionForm, RegisterForm, EndSessionForm

blueprint = Blueprint("users", __name__, url_prefix="/", static_folder="../static")
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

@blueprint.route(
    "/users/start-session",
    methods=["POST"],
)
def start_session():
    start_form = StartSessionForm()
    if not start_form.validate():
        return jsonify({"success": False, "errors": start_form.errors})

    existing = Session.get_active_session()

    if existing:
        log.info("Printer already in use by %s", existing.user.full_name)
        return jsonify({"success": False, "errors": {"user": ["Printer already in use"]}})
    
    session = Session(
        user=start_form.user,
        start_time=datetime.now(),
    )
    session.save()
    log.info("%s started session", start_form.user.full_name)

    socketio.emit("session_started", {"user": session.user.full_name,"start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, namespace="/users")

    return jsonify({"success": True})

@blueprint.route(
    "/users/register_user",
    methods=["POST"],
)
def register_user():
    register_form = RegisterForm()

    if not register_form.validate():
        return jsonify({"success": False, "errors": register_form.errors})
    
    user = User(
        first_name=register_form.first_name.data,
        last_name=register_form.last_name.data,
        email=register_form.email.data,
        username=register_form.username.data,
        password=register_form.password.data,
    )
    user.save()
    log.info("%s registered as %s", user.full_name, user.username)

    return jsonify({"success": True})

@blueprint.route("/users/end_session_modal_prints")
def end_session_modal_prints():
    return render_template("partials/end_session_modal_prints.html")

@blueprint.route(
    "/users/end_session",
    methods=["POST"],
)
def end_session():
    end_session_form = EndSessionForm()

    log.info("Ending session")

    if not end_session_form.validate():
        log.warning(f"Session form validation failed {end_session_form.errors}")
        return jsonify({"success": False, "errors": end_session_form.errors})
    
    log.info("Session ended")
    
    session = Session.get_active_session()

    #print print logs
    for print in end_session_form.prints:
        # print relavent info
        log.info("Print %s: Success=%s, Failure Mode=%s, Other Failure Mode=%s, Notes=%s", 
                 print.print_id.data, print.print_success.data, print.failure_mode.data, 
                 print.failure_detail.data, print.print_notes.data)

    # Update print information
    prints = session.print_records
    for print in prints:
        log.info("Updating print %s", print.id)
        # lookup print in form prints
        print_form = next((p for p in end_session_form.prints if int(p.print_id.data) == int(print.id)), None)
        if not print_form:
            continue

        log.info("Found form for print %s", print.id)


        # lookup failure mode
        if print_form.print_success.data == "no":
            # failure_mode = PrintRecord.FailureModeEnum(print_form.failure_mode.data)
            # log.info("Found failure mode for print %s: %s", print.id, failure_mode)
            print.failure_mode = print_form.failure_mode.data
        else:
            print.failure_mode = "NO_FAILURE"
        print.other_failure_mode = print_form.failure_detail.data if print_form.failure_detail.data else None
        print.notes = print_form.print_notes.data
        print.save()

    
    # Update calibration information (query all calibration records between start and end of session and remove all but the latest)
    calibrations = None
    if Calibration.query.order_by(Calibration.calibration_date.desc()).first() is not None:
        calibrations = Calibration.query.filter(
            Calibration.calibration_date >= session.start_time,
            Calibration.calibration_date <= datetime.now()
        ).all()

    if calibrations:
        # Keep only the latest calibration
        latest_calibration = max(calibrations, key=lambda x: x.calibration_date)
        # Do something with the latest calibration, e.g., update session with its data
        session.calibration_data = latest_calibration
        # Remove all other calibrations
        for calibration in calibrations:
            if calibration != latest_calibration:
                calibration.delete()
    else:
        # set session.calibration_data latest
        latest_calibration = Calibration.query.order_by(Calibration.calibration_date.desc()).first()


    # Update session information
    if session:
        session.end_time = datetime.now()
        # TODO: FOCUS
        session.film_changed = end_session_form.film_changed.data
        session.hardware_issues = end_session_form.printer_issues.data
        session.hardware_issues_details = end_session_form.printer_issue_details.data if end_session_form.printer_issue_details.data else None
        session.notes = end_session_form.session_notes.data
        session.save()
        log.info("%s ended session", session.user.full_name)

    socketio.emit("session_ended", namespace="/users")

    return jsonify({"success": True})


@socketio.on("connect", namespace="/users")
def connect():
    emit(
        "connected",
        dict(),
        namespace="/users",
        broadcast=False,
    )


@socketio.on("disconnect", namespace="/users")
def disconnect():
    log.debug("Socket disconnected %s", request.sid)