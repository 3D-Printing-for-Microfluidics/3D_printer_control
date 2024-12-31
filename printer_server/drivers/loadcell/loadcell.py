import time
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

        super().__init__("Loadcell", vid=config_dict["vendor_id"], pid=config_dict["product_id"], sn=config_dict["serial_number"],  baudrate=config_dict["baudrate"], timeout=0.1, line_ending='\n', multiline=True, logger=self.log)

        self.config_dict = config_dict
        self.currentData = []
        self.currentForce = 0
        self.start_time = 0
        self.running = False
        self.graph_newtons = True

        self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)
        self.log_file = None

    def adc_to_force(self, x):
        """
        Converts the adc counts to newtons using precalculated constants
        """
        grams = (x - self.config_dict["calibration_intercept"]) / self.config_dict["calibration_slope"]
        n = grams / 1000 * 9.8
        return n
    
    def initialize(self):
        try:
            self.stop()
            time.sleep(0.1)
            us = int(self.config_dict["sample_period_us"])
            self.log.debug("Period set to '%s'", us)
            self.set_sample_period(us)
        # It the server crashed, the loadcell may still be running. This will trigger and reset the connection
        except UnicodeDecodeError:
            self.disconnect()
            self.connect()
            self.stop()
            time.sleep(0.1)
            us = int(self.config_dict["sample_period_us"])
            self.log.debug("Period set to '%s'", us)
            self.set_sample_period(us)

    def disconnect(self):
        if self.connected:
            try:
                self.stop()
            except:
                pass
        super().disconnect()

    def start(self):
        """
        Starts the loadcell collecting data
        """
        if not self.thread.is_alive():
            self.running = True

            self.log.info("Loadcell started")
            loadcell_time = self.loadcell_start()

            if self.start_time == 0:
                self.start_time = datetime.datetime.now() - datetime.timedelta(
                    milliseconds=loadcell_time
                )
            time.sleep(0.1)
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
        time.sleep(0.1)
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

        time.sleep(0.1)
        self.flush_buffers()
        self.log.info("Loadcell stopped")
        self.start_time = 0

    def get_current_data(self):
        """
        Get current loadcell force
        """
        tmp = self.currentData
        self.currentData = []
        return tmp

    def get_current_force(self):
        """
        Get all current loadcell data
        """
        return self.currentForce

    def get_graph_mode(self):
        return self.graph_newtons

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
        self.log.debug("Starting loop")
        self.flush_buffers()
        self.read_until(b'\r\nAA')
        self.log.debug("Reached first new line")

        front_end_counter = 0
        front_end_array = []
        while self.running:
            try:
                
                milliseconds = int.from_bytes(
                    self.read_bytes(4), byteorder="little", signed=False
                )
                data = int.from_bytes(
                    self.read_bytes(2), byteorder="little", signed=False
                )
                time = self.start_time + datetime.timedelta(
                    milliseconds=float(milliseconds)
                )
                ret = self.read_until(b'\r\nAA')
                if len(ret) > 4:
                    self.log.debug("len(ret): %s", len(ret))
                    continue
                force = self.adc_to_force(data)

                if self.log_file is not None:
                    sys_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    loadcell_time = time.strftime("%Y-%m-%d %H:%M:%S.%f")
                    async_file_hander.write(
                        self.log_file,
                        f"{sys_time},{loadcell_time},{data},{force}\n",
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
            except SerialException as ex:
                self.currentForce = None
                self.currentData = None
                self.log.warning("Loadcell loop failed (%s)", ex, exc_info=True)
                self.running = False
            except ValueError as ex:
                self.log.warning("Unable to parse loadcell data - cast error (%s)", ex)
                continue
            except OverflowError as ex:
                self.log.warning("Unable to parse loadcell data - time overflow (%s)", ex)

    ########################
    # Teensy serial wrappers
    ########################

    def loadcell_start(self):
        """
        Sample at a frequency of freq (in Hz)
        """
        return self.send("b", parse_float_at_index=0)

    def loadcell_pause(self):
        """
        Pause sampling
        """
        self.send("p", recieve=False)

    def loadcell_stop(self):
        """
        Stop sampling
        """
        self.send("e", recieve=False)

    def set_sample_period(self, us):
        """
        Set the sampling period to us
        """
        self.send("t {}".format(us)), us
