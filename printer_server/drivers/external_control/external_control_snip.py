from printer_server.extensions import socketio


class External_Control:
    def __init__(self):
        self.enable_flag = False

    def set_enable(self, status):
        self.enable_flag = status

    def get_enable(self):
        return self.enable_flag


external_control_enable = External_Control()


@socketio.on("set_external_control_enable", namespace="/manual")
def set_external_control_enable(message):
    """set_external_control -- Sets the variable determining if printer can be auto-calibrated"""
    external_control_enable.set_enable(message == "Enabled")


@socketio.on("get_external_control_enable", namespace="/manual")
def get_external_control_enable(emit=True):
    """Return the external control enable flag."""
    socketio.emit(
        "external_control_enable",
        external_control_enable.get_enable(),
        namespace="/manual"
    )
    return external_control_enable.get_enable()
