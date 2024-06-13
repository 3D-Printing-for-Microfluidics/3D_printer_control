class MKSSolenoids_dummy():
    def __init__(self, *args, **kwargs):
        pass

    @dummy_log
    def connect(self, *args, **kwargs):
        return True
    
    @dummy_log
    def disconnect(self, *args, **kwargs):
        pass
            
    def activate_relay(self, *args, **kwargs):
        pass

    def deactivate_relay(self, *args, **kwargs):
        pass

    def get_statuses(self, *args, **kwargs):
        pass