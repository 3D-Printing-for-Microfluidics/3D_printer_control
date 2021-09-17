from printer_server.logging_handler import dummy_log


class Loadcell_dummy:
    @dummy_log
    def __init__(self, *args, **kwargs):
        pass

    @dummy_log
    def findUsbPort(self, *args, **kwargs):
        pass

    @dummy_log
    def adc_to_force(self, *args, **kwargs):
        pass

    @dummy_log
    def connect(self, *args, **kwargs):
        pass

    @dummy_log
    def start(self, *args, **kwargs):
        pass

    @dummy_log
    def set_log_file(self, *args, **kwargs):
        pass

    @dummy_log
    def pause(self, *args, **kwargs):
        pass

    @dummy_log
    def stop(self, *args, **kwargs):
        pass

    def get_current_data(self, *args, **kwargs):
        return  {
                    "timestamp": 0,
                    "index": 0,
                    "force": 0,
        }

    @dummy_log
    def get_current_force(self, *args, **kwargs):
        return 0

    @dummy_log
    def get_current_loadcell_index(self, *args, **kwargs):
        return 0

    @dummy_log
    def loop(self, *args, **kwargs):
        pass

    @dummy_log
    def write_to_file(self, *args, **kwargs):
        pass
