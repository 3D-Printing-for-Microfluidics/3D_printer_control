import math
import time
import threading

from printer_server.logging_handler import dummy_log


class Loadcell_dummy:
    @dummy_log
    def __init__(self, *args, **kwargs):
        self.graph_autoscale = False
        self.graph_newtons = True
        self.running = False
        self.thread = threading.Thread(target=self.loop)
        self.currentIndex = 0
        self.currentData = []
        self.currentForce = 0

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
        self.running = True
        self.thread.start()

    @dummy_log
    def set_log_file(self, *args, **kwargs):
        pass

    @dummy_log
    def pause(self, *args, **kwargs):
        if self.running:
            self.running = False
            self.thread.join()
            self.thread = threading.Thread(target=self.loop)
        self.currentForce = 0

    @dummy_log
    def stop(self, *args, **kwargs):
        if self.running:
            self.running = False
            self.thread.join()
            self.thread = threading.Thread(target=self.loop)
        self.currentForce = 0

    def get_current_data(self, *args, **kwargs):
        return self.currentData

    @dummy_log
    def get_current_force(self, *args, **kwargs):
        return self.currentForce

    @dummy_log
    def get_current_loadcell_index(self, *args, **kwargs):
        return self.currentIndex

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

    def loop(self, *args, **kwargs):
        """
        Threading loop
        """
        period = 4  # seconds
        sample_rate = 0.1
        while self.running:
            self.currentForce = 10 * math.cos(self.currentIndex)
            self.currentIndex += 2 * math.pi / period * sample_rate

            if len(self.currentData) >= 1:
                self.currentData.pop(0)
            self.currentData.append(
                {
                    "timestamp": time.time() * 1000,
                    "force": self.currentForce,
                }
            )

            time.sleep(sample_rate)
