import logging
from printer_server.logging_handler import dummy_log


class Planarization_dummy:
    @dummy_log
    def __init__(self, *args, log_level=logging.DEBUG, **kwargs):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.connected = None
        self.running = False

    def create_logs(self):
        pass

    @dummy_log
    def __init__(self, *args, log_level=logging.DEBUG, **kwargs):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.connected = None
        self.running = False

    @dummy_log
    def connect(self, *args, **kwargs):
        self.connected = True
    
    @dummy_log
    def disconnect(self, *args, **kwargs):
        self.connected = False
    
    @dummy_log
    def initialize(self, *args, **kwargs):
        pass

    @dummy_log
    def start(self, *args, **kwargs):
        self.running = True

    @dummy_log
    def set_log_file(self, *args, **kwargs):
        pass

    @dummy_log
    def stop(self, *args, **kwargs):
        self.running = False

    @dummy_log
    def loop(self, *args, **kwargs):
        pass

    @dummy_log
    def connect_hardware(self, *args, **kwargs):
        pass

    @dummy_log
    def initialize_hardware(self, *args, **kwargs):
        pass
