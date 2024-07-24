import threading

from printer_server.hardware_configuration import driver_handles
from printer_server.extensions import socketio
from printer_server.threading_wrapper import Thread
import printer_server.views.manual_controls

kdc = driver_handles.kdc101

# log = logging.getLogger(__name__)
# log.setLevel(logging.INFO)

@socketio.on("get_kdc_positions", namespace="/manual")
def get_kdc_positions(log=False, emit=True):
    last_positions = (
        printer_server.views.manual_controls.get_last_calibration_positions_from_logs()
    )
    last_positions["distance"] = kdc.getCurrentPos()

    if log:
        printer_server.views.manual_controls.write_to_position_log(last_positions)
    if emit:
        socketio.emit(
            "kdc_done",
            last_positions,
            namespace="/manual"
        )

    return last_positions

@socketio.on("kdc_motor_move", namespace="/manual")
def moveKDCMotor(message):
    distance_um = float(message["microns"])
    mode = message["mode"]
    mode = (
        mode != "absolute"
    )  # convert mode to True/False, absolute is true, all else is false
    kdc.move(distance_um, relative=mode)
    get_kdc_positions(log=message["log"])

@socketio.on("kdc_motor_home", namespace="/manual")
def homeKDCMotor(message):
    axis = message["axis"]

    def func(axis):
        kdc.home()
        get_kdc_positions(log=True)

    t = Thread(name="kdc101_snip_home_thread", target=func, args=[axis])
    t.start()
