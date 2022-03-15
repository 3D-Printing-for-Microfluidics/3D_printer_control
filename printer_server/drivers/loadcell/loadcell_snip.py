from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles

loadcell = driver_handles.loadcell


@socketio.on("loadcell_graph_mode", namespace="/manual")
def setLoadcellGraphMode(message):
    loadcell.set_graph_mode(message)


@socketio.on("loadcell_graph_autoscale", namespace="/manual")
def setLoadcellGraphAutoscale(message):
    loadcell.set_graph_autoscale(message)
