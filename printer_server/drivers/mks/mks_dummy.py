from printer_server.logging_handler import dummy_log

class MKS946_dummy():
    def __init__(self, *args, **kwargs):
        pass

    @dummy_log
    def connect(self, *args, **kwargs):
        return True
    
    @dummy_log
    def initialize(self, *args, **kwargs):
        pass

    @dummy_log
    def disconnect(self, *args, **kwargs):
        pass

    @dummy_log
    def read_pressure(self, channel):
        return 123
    
    @dummy_log
    def read_all_pressures(self):
        return [123, 123]

    @dummy_log
    def set_relay_mode(self, relay, state):
        pass

    @dummy_log
    def get_all_relay_status(self):
        tmp = []
        for i in range(12):
            tmp.append(False)
        return tmp