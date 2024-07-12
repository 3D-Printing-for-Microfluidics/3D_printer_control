import logging
import time

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class LightEngineDriver:
    def connect(self, shutdown):
        log.warn("Function not implemented. Using abstract LightEngineDriver class")

    def initialize(self):
        log.warn("Function not implemented. Using abstract LightEngineDriver class")

    def stop_sequencer(self):
        log.warn("Function not implemented. Using abstract LightEngineDriver class")

    def read_all_status(self, warn="ALL"):
        log.warn("Function not implemented. Using abstract LightEngineDriver class")

    def setup_exposure(self, exposure_time_ms, led_power=100, repeat=1, led_num=0):
        log.warn("Function not implemented. Using abstract LightEngineDriver class")

    def perform_exposure(self):
        log.warn("Function not implemented. Using abstract LightEngineDriver class")