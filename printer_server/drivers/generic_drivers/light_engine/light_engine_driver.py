import logging
import time

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class LightEngineDriver:
    def connect(self):
        log.warning("Function not implemented. Using abstract LightEngineDriver class")

    def initialize(self):
        log.warning("Function not implemented. Using abstract LightEngineDriver class")

    def stop_sequencer(self):
        log.warning("Function not implemented. Using abstract LightEngineDriver class")
    
    def idle_on(self):
        log.warning("Function not implemented. Using abstract LightEngineDriver class")

    def idle_off(self):
        log.warning("Function not implemented. Using abstract LightEngineDriver class")

    def read_all_status(self, warn="ALL"):
        log.warning("Function not implemented. Using abstract LightEngineDriver class")

    def setup_exposure(self, exposure_time_ms, led_power=100, repeat=1, led_num=0):
        log.warning("Function not implemented. Using abstract LightEngineDriver class")

    def perform_exposure(self):
        log.warning("Function not implemented. Using abstract LightEngineDriver class")

    def stop_sequencer(self):
        log.warning("Function not implemented. Using abstract LightEngineDriver class")

    def get_led_status(self):
        log.warning("Function not implemented. Using abstract LightEngineDriver class")