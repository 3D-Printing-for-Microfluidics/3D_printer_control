import logging
import time

import printer_server.views.home as home
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles
from printer_server.threading_wrapper import Thread

loadcell = driver_handles.loadcell

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def _send_manual_alert(msg):
    socketio.emit(
        "bootstrap alert",
        {"text": msg, "category": "warning"},
        namespace="/manual",
    )

def _emit_running_state():
    socketio.emit(
        "loadcell_return_running",
        loadcell.running,
        namespace="/manual",
    )

@socketio.on("loadcell_set_graph_mode", namespace="/manual")
def setLoadcellGraphMode(message):
    try:
        loadcell.set_graph_mode(message)
    except Exception as ex:
        log.warn("Loadcell manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "loadcell", namespace="/manual")

@socketio.on("loadcell_start", namespace="/manual")
def start_loadcell():
    try:
        loadcell.start()   
        time.sleep(0.5)
        if home.print_control.loadcell_thread is None:
            home.clear_loadcell_graph()
            home.print_control.loadcell_thread = Thread(log, name="print_control_loadcell_graph_loop_thread", target=home.print_control.loadcell_graph_loop)
            home.print_control.loadcell_thread.start()
        _emit_running_state()

    except Exception as ex:
        log.warn("Loadcell manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "loadcell", namespace="/manual")

@socketio.on("loadcell_stop", namespace="/manual")
def stop_loadcell():
    try:
        if home.print_control.state in ["planarizing", "printing"]:
            _send_manual_alert("Stop blocked: loadcell is required during planarization/printing.")
            _emit_running_state()
            return
        loadcell.stop()   
        time.sleep(0.5)
        if home.print_control.loadcell_thread is not None:
            home.print_control.loadcell_thread.join()
            home.print_control.loadcell_thread = None
            home.clear_loadcell_graph()
        _emit_running_state()

    except Exception as ex:
        log.warn("Loadcell manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "loadcell", namespace="/manual")

def get_graph_mode(emit=True):
    try:
        if emit:
            socketio.emit(
                "loadcell_return_graph_mode",
                loadcell.get_graph_mode(),
                namespace="/manual"
            )
        return loadcell.get_graph_mode()
    except Exception as ex:
        log.warn("Loadcell manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "loadcell", namespace="/manual")

def get_loadcell_state(emit=True):
    try:
        if emit:
            socketio.emit(
                "loadcell_return_running",
                loadcell.running,
                namespace="/manual",
            )
        return loadcell.running
    except Exception as ex:
        log.warn("Loadcell manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "loadcell", namespace="/manual")
