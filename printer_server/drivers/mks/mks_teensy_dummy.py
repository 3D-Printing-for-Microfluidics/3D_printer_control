from printer_server.logging_handler import dummy_log

class MKSTeensy_dummy():
    def __init__(self, *args, **kwargs):
        self.sensors = [0, 0, 0, 0, 0]
        self.relays = [0, 0, 0, 0, 0, 0, 0, 0, 0]

    @dummy_log
    def connect(self, *args, **kwargs):
        return True
    
    @dummy_log
    def disconnect(self, *args, **kwargs):
        pass
            
    @dummy_log
    def set_relay(self, relay_num, state, *args, **kwargs):
        self.relays[relay_num] = state

    @dummy_log
    def get_all_relay_status(self, *args, **kwargs):
        return self.relays

    @dummy_log
    def get_all_sensor_status(self, *args, **kwargs):
        return self.sensors
    
    @dummy_log
    def get_crane_position(self, *args, **kwargs):
        return 123
    
    @dummy_log
    def move_crane(self, *args, **kwargs):
        pass

    @dummy_log
    def move_crane_top(self):
        pass
        
    @dummy_log
    def move_crane_bottom(self):
        pass