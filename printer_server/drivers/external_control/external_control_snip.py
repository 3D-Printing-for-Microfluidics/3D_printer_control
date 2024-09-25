import logging
from printer_server.extensions import socketio
from printer_server.hardware_configuration.hardware_configuration import driver_handles
from printer_server.drivers.generic_drivers.bp_stage.bp_stage_snip import bp_get_position

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

external_control_enable = driver_handles.external_control
bp_stage = driver_handles.bp_stage

@socketio.on("external_control_set_enable", namespace="/manual")
def set_external_control_enable(message):
    """set_external_control -- Sets the variable determining if printer can be auto-calibrated"""
    try:
        if message == "Enabled":
            external_control_enable.set_enable(True)
            bp_stage.setUpperLimit(bp_stage.calibration_limit)
        else:
            external_control_enable.set_enable(False)
            bp_stage.setUpperLimit(bp_stage.bottom_limit)
        bp_get_position()
    except Exception as ex:
        log.warn("BP stage manual control failed (%s)", ex, exc_info=True)
        socketio.emit("hardware_failure", "bp", namespace="/manual")


@socketio.on("external_control_get_enable", namespace="/manual")
def get_external_control_enable(emit=True):
    """Return the external control enable flag."""
    socketio.emit(
        "external_control_return_enable",
        external_control_enable.get_enable(),
        namespace="/manual"
    )
    return external_control_enable.get_enable()
