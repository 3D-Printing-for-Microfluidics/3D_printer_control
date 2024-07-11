from printer_server.logging_handler import dummy_log

class MKSTeensy_dummy():
    def __init__(self, *args, **kwargs):
        self.switches = [0, 0, 0, 0, 0]
        self.relays = [0, 0, 0, 0, 0, 0, 0, 0, 0]

    @dummy_log
    def connect(self, *args, **kwargs):
        return True
    
    @dummy_log
    def disconnect(self, *args, **kwargs):
        pass
            
    def activate_relay(self, relay_num, *args, **kwargs):
        self.relays[relay_num] = 1

    def deactivate_relay(self, relay_num, *args, **kwargs):
        self.relays[relay_num] = 0

    def get_all_relay_status(self, *args, **kwargs):
        return self.relays

    def get_all_switch_status(self, *args, **kwargs):
        return self.switches