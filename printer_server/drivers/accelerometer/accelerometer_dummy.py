from printer_server.logging_handler import dummy_log


class Accelerometer_dummy:
    @dummy_log
    def __init__(self, *args, **kwargs):
        pass

    @dummy_log
    def connect(self, *args, **kwargs):
        return True

    @dummy_log
    def disconnect(self, *args, **kwargs):
        pass

    @dummy_log
    def findUsbPort(self, *args, **kwargs):
        pass

    @dummy_log
    def start(self, *args, **kwargs):
        pass

    @dummy_log
    def set_log_file(self, *args, **kwargs):
        pass

    @dummy_log
    def stop(self, *args, **kwargs):
        pass

    @dummy_log
    def loop(self, *args, **kwargs):
        pass

    @dummy_log
    def send(self, *args, **kwargs):
        pass

    @dummy_log
    def receive(self, *args, **kwargs):
        pass

    @dummy_log
    def receiveAll(self, *args, **kwargs):
        pass

    @dummy_log
    def accel_start(self, *args, **kwargs):
        pass

    @dummy_log
    def accel_pause(self, *args, **kwargs):
        pass

    @dummy_log
    def accel_stop(self, *args, **kwargs):
        pass

    @dummy_log
    def set_sample_frequency(self, *args, **kwargs):
        pass

    @dummy_log
    def send(self, *args, **kwargs):
        pass

    @dummy_log
    def receive(self, *args, **kwargs):
        pass

    @dummy_log
    def receive_bytes(self, *args, **kwargs):
        pass

    @dummy_log
    def receiveAll(self, *args, **kwargs):
        pass
