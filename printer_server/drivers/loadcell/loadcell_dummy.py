from printer_server.logging_handler import dummy_log


class Loadcell_dummy:
    @dummy_log
    def __init__(self, *args, **kwargs):
        self.graph_autoscale = False
        self.graph_newtons = True

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
        return {
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

    def get_graph_autoscale(self):
        return self.graph_autoscale

    def get_graph_mode(self):
        return self.graph_newtons

    @dummy_log
    def set_graph_autoscale(self, mode):
        if mode == "True":
            self.graph_autoscale = True
        elif mode == "False":
            self.graph_autoscale = False
        else:
            pass

    @dummy_log
    def set_graph_mode(self, mode):
        if mode == "Counts":
            self.graph_newtons = False
        elif mode == "Newtons":
            self.graph_newtons = True
        else:
            pass

    @dummy_log
    def loop(self, *args, **kwargs):
        pass

    @dummy_log
    def write_to_file(self, *args, **kwargs):
        pass
