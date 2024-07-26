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
        self.currentIndex = -1
        self.currentForce = 0
        self.start_time = 0
        self.running = False
        self.freq = 1000
        self.graph_newtons = True
        self.graph_autoscale = False

        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)
        self.log_file = None
        self.connected = False

    @dummy_log
    def adc_to_force(self, x):
        grams = (x - self.intercept) / self.slope
        n = grams / 1000 * 9.8
        return n

    @dummy_log
    def connect(self, frequency=1000):
        self.freq = frequency
        self.port = "dummyPort"
        if self.port is None:
            msg = "Loadcell not found!"
            self.log.critical(msg)
            return False
        self.connected = True
        self.loadcell_stop()
        self.receiveAll()
        self.set_sample_frequency(int(self.freq))
        self.log.info("Connected to loadcell (%s)", self.port)
        atexit.register(self.disconnect)
        return True

    @dummy_log
    def disconnect(self):
        if self.connected:
            self.connected = False
            self.log.info("Disconnected from Loadcell")

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
        try:
            self.loadcell_pause()
        except Exception:
            pass

        if self.running:
            self.running = False
            self.thread.join()
            self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)

        self.receiveAll()
        self.log.info("Loadcell paused")

    @dummy_log
    def stop(self):
        try:
            self.loadcell_stop()
        except Exception:
            pass

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
    def get_current_loadcell_index(self):
        return self.currentIndex

    # @dummy_log
    def get_graph_autoscale(self):
        return self.graph_autoscale

    # @dummy_log
    def get_graph_mode(self):
        return self.graph_newtons

    # @dummy_log
    def set_graph_autoscale(self, mode):
        self.graph_autoscale = mode == "True"

    # @dummy_log
    def set_graph_mode(self, mode):
        self.graph_newtons = mode == "Newtons"

    # @dummy_log
    def loop(self):
        front_end_counter = 0
        front_end_array = []
        while self.running:
            try:
                index = 0
                milliseconds = 0
                data = 0
                time = datetime.datetime.now()
                force = random.randrange(-40, 40, 1)

                if self.log_file is not None:
                    sys_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    loadcell_time = time.strftime("%Y-%m-%d %H:%M:%S.%f")
                    # Simulate file writing
                    with open(self.log_file, 'a') as f:
                        f.write(f"{sys_time},{loadcell_time},{index},{data},{force}\n")

                front_end_counter += 1
                if self.graph_newtons:
                    front_end_array.append(force)
                else:
                    front_end_array.append(data)
                if front_end_counter >= 10:
                    front_end_counter = 0
                    if len(self.currentData) >= 5:
                        self.currentData.pop(0)
                    self.currentData.append(
                        {
                            "timestamp": time.timestamp() * 1000,
                            "force": sum(front_end_array) / len(front_end_array),
                        }
                    )
                    front_end_array = []

                self.currentForce = force
                self.currentIndex = index
            except Exception as e:
                self.running = False
                self.log.warning("Exception in loadcell loop: %s", str(e))

    @dummy_log
    def loadcell_start(self):
        return "b"

    @dummy_log
    def loadcell_pause(self):
        try:
            self.send("p", receive=False)
        except Exception:
            pass

    @dummy_log
    def loadcell_stop(self):
        try:
            self.send("e", receive=False)
        except Exception:
            pass

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
    lc.connect()
    lc.start()
    lc.set_log_file("loadcell_data.txt")
    print(lc.get_current_force())
    lc.stop()
    lc.disconnect()