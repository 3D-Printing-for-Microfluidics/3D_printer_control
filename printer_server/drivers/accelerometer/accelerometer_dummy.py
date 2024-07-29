from printer_server.logging_handler import dummy_log


class Accelerometer_dummy:
    @dummy_log
    def __init__(self, *args, **kwargs):
        self.connected = None

    @dummy_log
    def connect(self, *args, **kwargs):
        return True
    
    @dummy_log
    def initialize(self, *args, **kwargs):
        return True

    @dummy_log
    def start(self, *args, **kwargs):
        pass

    @dummy_log
    def set_log_file(self, *args, **kwargs):
        pass

    @dummy_log
    def stop(self, *args, **kwargs):
        pass

    def loop(self, *args, **kwargs):
        pass

    @dummy_log
    def accel_start(self, *args, **kwargs):
        pass

    def accel_pause(self, *args, **kwargs):
        pass

    def accel_stop(self, *args, **kwargs):
        pass

    def set_sample_period(self, *args, **kwargs):
        pass
