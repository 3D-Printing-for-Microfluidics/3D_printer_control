import logging
import time
from printer_server.logging_handler import dummy_log
from printer_server.threading_wrapper import Thread


class Planarization_dummy:
    @dummy_log
    def __init__(self, config_dict=None, log_level=logging.DEBUG, *args, **kwargs):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.config_dict = config_dict or {}
        self.connected = None
        self.running = False
        self.log_file = None
        self.start_time = 0
        self.direction = None
        self.current_torque_kgmm = 0.0
        self._simulate_thread = None

        self.default_torque_target_kgmm = float(
            self.config_dict.get("target_torque_kgmm", 40.0)
        )
        self.torque_target_kgmm = self.default_torque_target_kgmm

    def create_logs(self):
        pass

    @dummy_log
    def connect(self, *args, **kwargs):
        self.connected = True
    
    @dummy_log
    def disconnect(self, *args, **kwargs):
        self.connected = False
    
    @dummy_log
    def initialize(self, *args, **kwargs):
        pass

    @dummy_log
    def start(self, direction="tighten", torque_kgmm=None, *args, **kwargs):
        if torque_kgmm is None:
            torque_kgmm = (
                self.default_torque_target_kgmm
                if direction == "tighten"
                else 0.0
            )
        self.set_torque_target_kgmm(torque_kgmm)
        self.direction = direction
        self.running = True
        if direction == "tighten":
            self.current_torque_kgmm = self.torque_target_kgmm
        else:
            self.current_torque_kgmm = 0.0
        self._start_simulation()

    @dummy_log
    def set_log_file(self, filename=None, *args, **kwargs):
        self.log_file = filename

    @dummy_log
    def stop(self, *args, **kwargs):
        self.running = False

    @dummy_log
    def set_torque_target_kgmm(self, kgmm):
        if kgmm is None:
            return
        self.torque_target_kgmm = float(kgmm)

    def _start_simulation(self):
        if self._simulate_thread is not None and self._simulate_thread.is_alive():
            return
        self._simulate_thread = Thread(
            self.log,
            name="planarization_dummy_sim_thread",
            target=self._simulate_run,
        )
        self._simulate_thread.start()

    def _simulate_run(self):
        delay = max(0.05, min(0.3, abs(self.torque_target_kgmm) * 0.005))
        time.sleep(delay)
        self.running = False

    @dummy_log
    def loop(self, *args, **kwargs):
        pass

    @dummy_log
    def connect_hardware(self, *args, **kwargs):
        pass

    @dummy_log
    def initialize_hardware(self, *args, **kwargs):
        pass
