import logging

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class TTRStageDriver:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.initialized = None

    def connect(self, shutdown):
        log.warn("Function not implemented. Using abstract TTRStageDriver class")

    def initialize(self):
        log.warn("Function not implemented. Using abstract TTRStageDriver class")
