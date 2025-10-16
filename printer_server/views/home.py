import time
import json
from pathlib import Path
import logging
import signal
from flask import Blueprint, request, render_template
from flask_socketio import join_room, leave_room, emit

from printer_server.settings import Config
from printer_server.models import PrintQueue
from printer_server.extensions import socketio
from printer_server.views.manual_controls import stop_loop
from printer_server.hardware_configuration.hardware_configuration import config_dict
from printer_server.printer_control.print_control import PrintControl, PrintingException, run_in_thread

blueprint = Blueprint("home", __name__, url_prefix="/", static_folder="../static")
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

parent_classes = []

from printer_server.printer_control.test_control import TestControl
parent_classes.append(TestControl)   

# film gpio needs to be before bp
if "gpio" in config_dict:
    gpio_imported = False
    if "film_pin" in config_dict["gpio"]:
        from printer_server.printer_control.gpio_control import FilmGPIOControl
        parent_classes.append(FilmGPIOControl)   
        gpio_imported = True
    if "wintech_fan_pin1" in config_dict["gpio"]:
        from printer_server.printer_control.gpio_control import WintechFanGPIOControl
        parent_classes.append(WintechFanGPIOControl)   
        gpio_imported = True
    if not gpio_imported:
        from printer_server.printer_control.gpio_control import GPIOControl
        parent_classes.append(GPIOControl)   

# MKS needs to be before loadcell
if "mks" in config_dict.keys() and "mks_teensy" in config_dict.keys():
    from printer_server.printer_control.vacuum_control import VacuumControl
    parent_classes.append(VacuumControl)

# Loadcell needs to be before bp
if "loadcell" in config_dict:
    from printer_server.printer_control.loadcell_control import LoadcellControl
    parent_classes.append(LoadcellControl)

# planarization must be before bp_stage and after loadcell
if "planarization" in config_dict:
    from printer_server.printer_control.planarization_control import PlanarizationControl
    parent_classes.append(PlanarizationControl)

if "bp_stage" in config_dict["stages"]:
    from printer_server.printer_control.bp_control import BPControl
    parent_classes.append(BPControl)

if "environmental_sensors" in config_dict:
    from printer_server.printer_control.environmental_sensors_control import EnvironmentalSensorsControl
    parent_classes.append(EnvironmentalSensorsControl)

if "accelerometer" in config_dict:
    from printer_server.printer_control.accelerometer_control import AccelerometerControl
    parent_classes.append(AccelerometerControl)

# keyence needs to be before focus
if "keyence" in config_dict:
    from printer_server.printer_control.keyence_focus_control import KeyenceFocusControl
    parent_classes.append(KeyenceFocusControl)

if "focus_stage" in config_dict["stages"]:
    from printer_server.printer_control.focus_control import FocusControl
    parent_classes.append(FocusControl)

if "light_engines" in config_dict:
    from printer_server.printer_control.screen_control import ScreenControl
    from printer_server.printer_control.light_engine_control import LightEngineControl
    parent_classes.append(LightEngineControl)

if "spectrometer" in config_dict or "photodiode" in config_dict:
    from printer_server.printer_control.light_measurement_control import LightMeasurementControl
    parent_classes.append(LightMeasurementControl)

if "ttr_stage" in config_dict["stages"]:
    from printer_server.printer_control.ttr_control import TTRControl
    parent_classes.append(TTRControl)

if "xy_stage" in config_dict["stages"]:
    from printer_server.printer_control.xy_control import XYControl
    parent_classes.append(XYControl)


class BasePrintControl(*parent_classes):
    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self):
        try:
            super().planarization_step_1()
        except PrintingException:
            self.printing_stopped.set()
            self.critical_error_handle("printing")     
            return False

    @run_in_thread("planarized", "Planarization Step 2")
    def planarization_step_2(self):
        try:
            super().planarization_step_2()
        except PrintingException:
            self.printing_stopped.set()
            self.critical_error_handle("printing")    
            return False

    @run_in_thread("initialized", "Cancel Planarization")
    def cancel_planarization(self):
        try:
            super().cancel_planarization()
        except PrintingException:
            self.printing_stopped.set()
            self.critical_error_handle("printing")    
            return False

    @run_in_thread("planarized", "Automatic Planarization")
    def combined_planarization(self):
        try:
            self.planarization_step_1()
            self.state = "planarizing"
            self.planarization_step_2()
        except PrintingException:
            self.printing_stopped.set()
            self.critical_error_handle("printing")    
            return False

    def start(self, job_id):
        try:
            super().start(job_id)
        except PrintingException:
            self.printing_stopped.set()
            self.critical_error_handle("printing")    
            return False

    @run_in_thread("paused", "Pause Printing")
    def pause(self):
        try:
            super().pause()
        except PrintingException:
            self.printing_stopped.set()
            self.critical_error_handle("printing")    
            return False

    def resume(self):
        try:
            super().resume()
        except PrintingException:
            self.printing_stopped.set()
            self.critical_error_handle("printing")    
            return False

    @run_in_thread("stopped", "Stop Printing")
    def stop(self):
        try:
            super().stop()
        except PrintingException:
            self.printing_stopped.set()
            self.critical_error_handle("printing")    
            return False

    def print_worker(self):
        try:
            super().print_worker()
        except PrintingException:
            self.printing_stopped.set()
            self.critical_error_handle("printing")    
            return False

print_control = BasePrintControl()

@blueprint.route("/")
def index():
    allJobs = PrintQueue.query.all()

    kwargs = {
        "allJobs":allJobs,
        "hostname":Config.HOSTNAME
    }

    kwargs["loadcell_exists"] = "loadcell" in config_dict.keys()

    if "mks" in config_dict.keys() and "mks_teensy" in config_dict.keys():
        kwargs["degas_state"] = print_control.degas_state

    return render_template(
        "home.html",
        **kwargs
    )

def update_printer_state(state, msg):
    socketio.emit(state, msg, namespace="/printing")

if "loadcell" in config_dict.keys():
    def clear_loadcell_graph():
        socketio.emit("loadcell_graph_clear", namespace="/printing")


    def update_loadcell_graph(msg):
        socketio.emit("loadcell_graph_data", msg, namespace="/printing", to="loadcell")


def send_bootstrap_alert(msg):
    socketio.emit(
        "bootstrap alert",
        {"text": msg, "category": "warning"},
        namespace="/printing",
    )

critical_error_val = None

@socketio.on("connect", namespace="/printing")
def connect():
    emit(
        print_control.state,
        dict(),
        namespace="/printing",
        broadcast=False,
    )
    if critical_error_val is not None:
        critical_error(critical_error_val)


@socketio.on("disconnect", namespace="/printing")
def disconnect():
    log.debug("Socket disconnected %s", request.sid)


@socketio.on("initialize", namespace="/printing")
# pylint: disable=unused-argument
def initialize(message):
    # classes = ""
    # for c in BasePrintControl.__mro__:
    #     classes += c.__name__ + ", "
    # classes = classes[:-2]
    # log.warn(classes)
    print_control.initialize(critical_error, run_in_thread=False, top_level=True)


def critical_error(process):
    global critical_error_val
    critical_error_val = process
    if process == "initialization":
        title = "Initialization Failed"
        msg = "The following hardware was not found:\n"
        for name in print_control.failed_hardware.keys():
            msg += f"\t- {name}\n"
        msg += "Click 'Confirm' to retry initialization..."
    elif process == "printing":
        title = "Print Failed"
        msg = "A unrecoverable error occurred during printing in the following hardware:\n"
        for name in print_control.failed_hardware.keys():
            msg += f"\t- {name}\n"
        msg += "Printer must restart. Click 'Confirm' to continue..."
    time.sleep(1.0)
    socketio.emit("critical_error", {"process": process, "title": title, "message": msg}, namespace="/printing")


@socketio.on("critical_error_confirm", namespace="/printing")
# pylint: disable=unused-argument
def critical_error_confirm(message):
    global critical_error_val
    critical_error_val = None
    if message == "initialization":
        print_control.reinitialize(run_in_thread=False, top_level=True)
    elif message == "printing":
        shutdown()


@socketio.on("critical_error_cancel", namespace="/printing")
# pylint: disable=unused-argument
def critical_error_reply(message):
    global critical_error_val
    critical_error_val = None
    if message == "initialization":
        shutdown()


@socketio.on("planarization step 1", namespace="/printing")
# pylint: disable=unused-argument
def planarization_step_1(message):
    if "planarization" in config_dict:
        print_control.combined_planarization(run_in_thread=True, top_level=True)
    else:
        print_control.planarization_step_1(run_in_thread=True, top_level=True)


@socketio.on("planarization step 2", namespace="/printing")
# pylint: disable=unused-argument
def planarization_step_2(message):
    print_control.planarization_step_2(run_in_thread=True, top_level=True)

@socketio.on("cancel planarization", namespace="/printing")
# pylint: disable=unused-argument
def cancel_planarization(message):
    print_control.cancel_planarization(run_in_thread=True, top_level=True)

@socketio.on("start", namespace="/printing")
# pylint: disable=unused-argument
def start_print(message):
    print_control.start(message["job"])


@socketio.on("pause", namespace="/printing")
# pylint: disable=unused-argument
def pause_print(message):
    print_control.pause(run_in_thread=True, top_level=True)


@socketio.on("resume", namespace="/printing")
# pylint: disable=unused-argument
def resume_print(message):
    print_control.resume()


@socketio.on("stop", namespace="/printing")
# pylint: disable=unused-argument
def stop(message):
    print_control.stop(run_in_thread=True, top_level=True)


@socketio.on("degas", namespace="/printing")
def degas(msg):
    print_control.degas(msg)


@socketio.on("shutdown", namespace="/printing")
# pylint: disable=unused-argument
def shutdown(message="critical"):
    is_critical = True
    if message != "critical":
        is_critical = False
    stop_loop(force=True)
    print_control.shutdown(is_critical)
    

def shutdown_exception(exception, trace):
    shutdown()
signal.signal(signal.SIGINT, shutdown_exception)

if "loadcell" in config_dict.keys():
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
