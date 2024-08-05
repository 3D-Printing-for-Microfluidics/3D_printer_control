import time
import logging
import datetime
from serial import SerialException
from printer_server.threading_wrapper import Thread
from printer_server.drivers.generic_drivers import USBSerial
from printer_server.async_file_handler import async_file_hander


class Accelerometer(USBSerial):

    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        """
        Initializes the accelerometer
        """
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__("Accelerometers", vid=config_dict["vendor_id"], pid=config_dict["product_id"], sn=config_dict["serial_number"], baudrate=config_dict["baudrate"], timeout=0.1, line_ending='\n', logger=self.log)

        self.config_dict = config_dict
        self.start_time = 0
        self.running = False

        self.thread = Thread(self.log, name="accelerometer_loop_thread", target=self.loop)
        self.log_file = None

    def initialize(self):
        self.stop()
        us = int(self.config_dict["measurement_period_us"])
        self.log.debug("Period set to '%s'", us)
        self.set_sample_period(us)

    def disconnect(self):
        if self.connected:
            self.stop()
        super().disconnect()

    def start(self):
        """
        Starts the accelerometer collecting data
        """
        if not self.thread.is_alive():
            self.running = True

            self.log.info("Accelerometer started")
            temp = self.accel_start()
            if self.start_time == 0:
                accel_time = temp.split("'")
                accel_time = float(accel_time[1])
                self.start_time = datetime.datetime.now() - datetime.timedelta(
                    milliseconds=accel_time
                )
            time.sleep(0.1)
            self.thread.start()

    def set_log_file(self, filename):
        """
        Sets the filepath to save the log to

        Parameters:
            filename    - local path and filename (current_job/accelerometer_data.txt)
        """
        self.log_file = filename

    def pause(self):
        """
        Pauses the accelerometer and accelerometer thread.
        """
        self.accel_pause()

        if self.running:
            self.running = False
            self.thread.join()
            self.thread = Thread(self.log, name="accelerometer_loop_thread", target=self.loop)

        time.sleep(0.1)
        self.flush_buffers()
        self.log.info("Accelerometer paused")

    def stop(self):
        """
        Stops the accelerometer and accelerometer thread. Saves data to file
        """
        self.accel_stop()

        if self.running:
            self.running = False
            self.thread.join()
            self.thread = Thread(self.log, name="accelerometer_loop_thread", target=self.loop)

        time.sleep(0.1)
        self.flush_buffers()
        self.log.info("Accelerometer stopped")
        self.start_time = 0

    def loop(self):
        """
        Threading loop
        """
        self.log.debug("Starting loop")
        self.flush_buffers()
        ret = self.read_bytes(1)
        while ret != b'\n':
            if not self.running:
                return
            bad_data = True
            ret = self.read_bytes(1)
        self.log.debug("Reached first new line")

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
                    if not self.running:
                        return
                    bad_data = True
                    ret = self.read_bytes(1)
                if bad_data:
                    continue
                accel = data/16384

                if self.log_file is not None:
                    sys_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    accel_time = time.strftime("%Y-%m-%d %H:%M:%S.%f")
                    async_file_hander.write(
                        self.log_file,
                        f"{sys_time},{accel_time},{index},{accel}\n",
                    )
            except SerialException:
                self.running = False
            except ValueError:
                self.log.warning("Unable to parse Accelerometer data - cast error")
                continue
            except OverflowError:
                self.log.warning("Unable to parse Accelerometer data - time overflow")

    ########################
    # Teensy serial wrappers
    ########################

    def accel_start(self):
        """
        Sample at a frequency of freq (in Hz)
        """
        return self.send("b")

    def accel_pause(self):
        """
        Pause sampling
        """
        self.send("p", recieve=False)

    def accel_stop(self):
        """
        Stop sampling
        """
        self.send("e", recieve=False)


    def set_sample_period(self, ms):
        """
        Set the sampling period to ms (in ms)
        """
        return self.send("t {}".format(ms)), ms
