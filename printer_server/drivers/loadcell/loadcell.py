import logging
import datetime
from serial import SerialException
from printer_server.threading_wrapper import Thread
from printer_server.drivers.generic_drivers import USBSerial
from printer_server.async_file_handler import async_file_hander


class LoadCell(USBSerial):
    """
    Class providing high level control of loadcell
    """

    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        """
        Initializes the loadcell
        """
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__(vid=config_dict["vendor_id"], pid=config_dict["product_id"], sn=config_dict["serial_number"],  baudrate=config_dict["baudrate"], timeout=1, line_ending='\n', logger=self.log)

        self.intercept = config_dict["calibration_intercept"]
        self.slope = config_dict["calibration_slope"]

        self.currentData = []
        self.currentIndex = -1
        self.currentForce = 0
        self.start_time = 0
        self.running = False
        self.freq = 1000
        self.graph_newtons = True
        self.graph_autoscale = False

        self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)
        self.log_file = None

    def adc_to_force(self, x):
        """
        Converts the adc counts to newtons using precalculated constants
        """
        grams = (x - self.intercept) / self.slope
        n = grams / 1000 * 9.8
        return n
    
    def initialize(self, frequency=1000):
        self.freq = frequency
        self.loadcell_stop()
        self.flush_buffers()
        self.log.debug("%s", self.set_sample_frequency(int(self.freq)))

    def disconnect(self):
        if self.connected:
            if self.running:
                self.running = False
                self.thread.join()
                self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)
        super().disconnect()

    def start(self):
        """
        Starts the loadcell collecting data
        """
        if not self.thread.is_alive():
            self.running = True

            self.log.info("Loadcell started")
            temp = self.loadcell_start()
            if self.start_time == 0:
                loadcell_time = temp.split("'")
                loadcell_time = float(loadcell_time[1])
                self.start_time = datetime.datetime.now() - datetime.timedelta(
                    milliseconds=loadcell_time
                )
            self.thread.start()

    def set_log_file(self, filename):
        """
        Sets the filepath to save the log to

        Parameters:
            filename    - local path and filename (current_job/loadcell_data.txt)
        """
        self.log_file = filename

    def pause(self):
        """
        Pauses the loadcell and loadcell thread.
        """
        self.loadcell_pause()

        if self.running:
            self.running = False
            self.thread.join()
            self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)

        self.flush_buffers()

        self.log.info("Loadcell paused")

    def stop(self):
        """
        Stops the loadcell and loadcell thread. Saves data to file
        """
        self.loadcell_stop()

        if self.running:
            self.running = False
            self.thread.join()
            self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)

        self.flush_buffers()

        self.log.info("Loadcell stopped")
        self.start_time = 0

    def get_current_data(self):
        """
        Get current loadcell force
        """
        return self.currentData

    def get_current_force(self):
        """
        Get all current loadcell data
        """
        return self.currentForce

    def get_current_loadcell_index(self):
        """
        Get all current loadcell data
        """
        return self.currentIndex

    def get_graph_autoscale(self):
        return self.graph_autoscale

    def get_graph_mode(self):
        return self.graph_newtons

    def set_graph_autoscale(self, mode):
        if mode == "True":
            self.graph_autoscale = True
        elif mode == "False":
            self.graph_autoscale = False
        else:
            pass

    def set_graph_mode(self, mode):
        if mode == "Counts":
            self.graph_newtons = False
        elif mode == "Newtons":
            self.graph_newtons = True
        else:
            pass

    def loop(self):
        """
        Threading loop
        """
        front_end_counter = 0
        front_end_array = []
        while self.running:
            try:
                index = int.from_bytes(
                    self.read_bytes(4), byteorder="little", signed=False
                )
                milliseconds = int.from_bytes(
                    self.read_bytes(4), byteorder="little", signed=False
                )
                data = int.from_bytes(
                    self.read_bytes(2), byteorder="little", signed=False
                )
                time = self.start_time + datetime.timedelta(
                    milliseconds=float(milliseconds)
                )
                bad_data = False
                ret = self.read_bytes(1)
                while ret != b'\n':
                    bad_data = True
                    ret = self.read_bytes(1)
                if bad_data:
                    continue
                force = self.adc_to_force(data)

                if self.log_file is not None:
                    sys_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    loadcell_time = time.strftime("%Y-%m-%d %H:%M:%S.%f")
                    async_file_hander.write(
                        self.log_file,
                        f"{sys_time},{loadcell_time},{index},{data},{force}\n",
                    )

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
            except SerialException:
                self.running = False
            except ValueError:
                self.log.warning("Unable to parse loadcell data - cast error")
                continue
            except OverflowError:
                self.log.warning("Unable to parse loadcell data - time overflow")

    ########################
    # Teensy serial wrappers
    ########################

    def loadcell_start(self):
        """
        Sample at a frequency of freq (in Hz)
        """
        return self.send("b")

    def loadcell_pause(self):
        """
        Pause sampling
        """
        self.send("p", recieve=False)
        return

    def loadcell_stop(self):
        """
        Stop sampling
        """
        self.send("e", recieve=False)
        return

    def set_sample_frequency(self, freq_hz):
        """
        Set the sampling frequency to freq_hz (in hz)
        """
        self.log.debug("Frequency set to '%s'", freq_hz)
        return self.send("f {}".format(freq_hz)), freq_hz
