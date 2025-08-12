import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

planar = getattr(driver_handles, "planarization")

def _planar_status_dict():
    try:
        running = bool(getattr(planar, "running", False))
        tgt = getattr(planar, "torque_target_kgmm", None)
        return {"running": running, "torque_target_kgmm": f"{tgt:.3f}" if tgt is not None else None}
    except Exception as ex:
        log.warning("Planarization status failed (%s)", ex, exc_info=True)
        return {"running": False, "torque_target_kgmm": None}

@socketio.on("planar_status_query", namespace="/manual")
def planar_status_query():
    """Return current running + target torque."""
    socketio.emit("planar_status", _planar_status_dict(), namespace="/manual")

@socketio.on("planar_set_target", namespace="/manual")
def planar_set_target(message):
    """Set target torque only (kg·mm)."""
    try:
        torque = float(message.get("torque_kgmm"))
        planar.set_torque_target_kgmm(torque)
        socketio.emit("planar_status", _planar_status_dict(), namespace="/manual")
    except Exception as ex:
        log.warning("Planarization set target failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "planar", namespace="/manual")

@socketio.on("planar_start", namespace="/manual")
def planar_start(message):
    """Begin tighten/untighten to the target torque."""
    try:
        direction = message.get("direction", "tighten")
        torque = message.get("torque_kgmm", None)
        torque = float(torque) if torque is not None else None
        planar.start(direction=direction, torque_kgmm=torque)
        socketio.emit("planar_status", _planar_status_dict(), namespace="/manual")
        # Optional: if you later want push completion, run a tiny watcher thread here.
    except Exception as ex:
        log.warning("Planarization start failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "planar", namespace="/manual")

@socketio.on("planar_stop", namespace="/manual")
def planar_stop():
    """Emergency stop."""
    try:
        planar.stop()
        socketio.emit("planar_status", _planar_status_dict(), namespace="/manual")
    except Exception as ex:
        log.warning("Planarization stop failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "planar", namespace="/manual")
