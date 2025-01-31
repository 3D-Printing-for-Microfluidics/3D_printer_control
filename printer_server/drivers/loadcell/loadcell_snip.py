import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles

loadcell = driver_handles.loadcell

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

@socketio.on("loadcell_set_graph_mode", namespace="/manual")
def setLoadcellGraphMode(message):
    try:
        loadcell.set_graph_mode(message)
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
