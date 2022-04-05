import time

from printer_server.logging_handler import dummy_log


class Wintech_dummy:
    @dummy_log
    def __init__(self):
        self.led_on = False
        self.exposure_time = 0

    @dummy_log
    def connect(self):
        pass

    @dummy_log
    def stop_sequencer(self):
        self.led_on = False

    @dummy_log
    def setup_exposure(self, t, p, r=1):
        self.exposure_time = t
        min_t = 4.046
        max_t = 10000
        if t > max_t:
            t = max_t
            self.exposure_time = max_t
        elif t < min_t:
            t = min_t
            self.exposure_time = min_t

    @dummy_log
    def perform_exposure(self):
        self.led_on = True
        if self.exposure_time != 0:
            time.sleep(self.exposure_time * 1e-3)
        self.led_on = False

    @dummy_log
    def project(self, exposure_time_ms, led_power=100, repeat=1):
        min_t = 4.046
        max_t = 10000
        self.led_on = True
        if exposure_time_ms > max_t:
            exposure_time_ms = max_t
        elif min_t > exposure_time_ms:
            exposure_time_ms = min_t
        if repeat == 0:
            pass
        else:
            time.sleep(exposure_time_ms * 0.001 + 0.1)
            self.led_on = False
