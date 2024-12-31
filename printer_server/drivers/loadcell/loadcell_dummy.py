import math
import time
import atexit
import random
import logging
import datetime
import threading

from printer_server.logging_handler import dummy_log
from printer_server.threading_wrapper import Thread


class Loadcell_dummy:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.port = None
        self.intercept = config_dict["calibration_intercept"] if config_dict else 0
        self.slope = config_dict["calibration_slope"] if config_dict else 1
        self.currentData = []
        self.currentForce = 0
        self.start_time = 0
        self.running = False
        self.freq = 1000
        self.graph_newtons = True

        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)
        self.log_file = None
        self.connected = False

    # @dummy_log
    def adc_to_force(self, x):
        grams = (x - self.intercept) / self.slope
        n = grams / 1000 * 9.8
        return n

    @dummy_log
    def connect(self, frequency=1000):
        self.freq = frequency
        self.port = "dummyPort"
        self.connected = True
        self.loadcell_stop()
        self.receiveAll()
        self.set_sample_frequency(int(self.freq))
        atexit.register(self.disconnect)
        return True

    @dummy_log
    def disconnect(self):
        if self.connected:
            self.connected = False
            self.log.info("Disconnected from Loadcell")

    @dummy_log
    def initialize(self):
        pass

    @dummy_log
    def start(self):
        if not self.thread.is_alive():
            self.running = True
            self.flushInput()
            self.log.info("Loadcell started")
            temp = self.loadcell_start()
            if self.start_time == 0:
                self.start_time = datetime.datetime.now()
            self.thread.start()

    @dummy_log
    def set_log_file(self, filename):
        self.log_file = filename

    @dummy_log
    def pause(self):
        self.loadcell_pause()

        if self.running:
            self.running = False
            self.thread.join()
            self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)

        self.receiveAll()
        self.log.info("Loadcell paused")

    @dummy_log
    def stop(self):
        self.loadcell_stop()

        if self.running:
            self.running = False
            self.thread.join()
            self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)

        self.receiveAll()
        self.log.info("Loadcell stopped")
        self.start_time = 0

    # @dummy_log
    def get_current_data(self):
        return self.currentData

    # @dummy_log
    def get_current_force(self):
        return self.currentForce

    # @dummy_log
    def get_graph_mode(self):
        return self.graph_newtons

    # @dummy_log
    def set_graph_mode(self, mode):
        self.graph_newtons = mode == "Newtons"

    # @dummy_log
    def loop(self):
        while self.running:
            try:
                data = 0
                t = datetime.datetime.now()
                force = random.randrange(-40, 40, 1)

                if self.log_file is not None:
                    sys_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    loadcell_time = t.strftime("%Y-%m-%d %H:%M:%S.%f")
                    with open(self.log_file, 'a') as f:
                        f.write(f"{sys_time},{loadcell_time},{data},{force}\n")

                if self.graph_newtons:
                    self.currentData.append(
                    {
                        "timestamp": t.timestamp() * 1000,
                        "force": force,
                    }
                )
                else:
                    self.currentData.append(
                    {
                        "timestamp": t.timestamp() * 1000,
                        "force": data,
                    }
                )
                if len(self.currentData) >= 5:
                    self.currentData.pop(0)

                self.currentForce = force
                time.sleep(0.01)

            except Exception as ex:
                self.running = False
                self.log.warning("Exception in loadcell loop: %s", str(ex))

    @dummy_log
    def loadcell_start(self):
        return "b"

    @dummy_log
    def loadcell_pause(self):
        self.send("p", receive=False)

    @dummy_log
    def loadcell_stop(self):
        self.send("e", receive=False)

    # @dummy_log
    def set_sample_frequency(self, freq_hz):
        self.log.debug("Frequency set to '%s'", freq_hz)
        return self.send("f {}".format(freq_hz)), freq_hz

    # @dummy_log
    def send(self, cmd, receive=True):
        self.log.debug("Sent: '%s'", cmd)
        if receive:
            response = self.receive()
            self.log.debug("Response: '%s'", response)
            return response
        return

    # @dummy_log
    def receive(self):
        return "Done"

    # @dummy_log
    def read_bytes(self, number_of_bytes):
        return b'\x00' * number_of_bytes

    # @dummy_log
    def receiveAll(self):
        return

    # @dummy_log
    def flushInput(self):
        return

if __name__ == "__main__":
    config = {
        "calibration_intercept": 0,
        "calibration_slope": 1
    }
    lc = Loadcell_dummy(config_dict=config)
    lc.connect(exit)
    lc.start()
    lc.set_log_file("loadcell_data.txt")
    print(f"{lc.get_current_force()}")
    lc.stop()
    lc.disconnect()