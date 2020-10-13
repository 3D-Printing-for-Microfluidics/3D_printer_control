from printer_server.logging_handler import dummy_log

class Loadcell_dummy:
    @dummy_log
    def __init__(self, *args, **kwargs):
        pass

    @dummy_log
    def connect(self, *args, **kwargs):
        pass

    @dummy_log
    def start(self, *args, **kwargs):
        pass
        
    @dummy_log
    def stop(self, *args, **kwargs):
        pass
        
    @dummy_log
    def pause(self, *args, **kwargs):
        pass

    @dummy_log
    def loop(self, *args, **kwargs):
        pass
        
    @dummy_log
    def get_data(self, *args, **kwargs):
        pass

    @dummy_log
    def adc_to_force(self, *args, **kwargs):
        pass
        
    @dummy_log
    def process_data(self, *args, **kwargs):
        pass
