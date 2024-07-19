from printer_server.logging_handler import dummy_log


class Accelerometer_dummy:
    @dummy_log
    def __init__(self, *args, **kwargs):
        pass
