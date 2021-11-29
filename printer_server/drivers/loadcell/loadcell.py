import atexit
import logging
import datetime
import threading
import serial
import serial.tools.list_ports
import serial.serialutil
from printer_server.async_file_handler import async_file_hander


class LoadCell(serial.Serial):
    """
    Class providing high level control of loadcell
    """

    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        """
        Initializes the loadcell
        """
        super().__init__(baudrate=115200, timeout=1)
        self.port = None  # start with no port
        # self.status = None              # status to be updated after every send

        self.hwid = config_dict["hwid"]
        self.intercept = config_dict["calibration_intercept"]
        self.slope = config_dict["calibration_slope"]

        self.currentData = []
        self.currentIndex = -1
        self.currentForce = 0
        self.start_time = 0
        self.running = False
        self.freq = 1000

        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.thread = threading.Thread(target=self.loop)
        self.log_file = None

    def findUsbPort(self, hwid):
        """
        Finds serial port with given hwid

        Parameters:
            hwid - device identifier
        """
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            if hwid.upper() in p.hwid:
                self.log.debug("Found '%s' at '%s'", p.hwid, p.device)
                return p.device
        return None  # not found

    def adc_to_force(self, x):
        """
        Converts the adc counts to newtons using precalculated constants
        """

        grams = (x - self.intercept) / self.slope
        n = grams / 1000 * 9.8
        return n

    def connect(self, frequency=1000):
        """
        Connects to the loadcell and sets parameters.

        Parameters:
            hwid        - device identifier
            frequency   - sample frequency of loadcell (in milliseconds)
        """
        self.freq = frequency

        self.port = self.findUsbPort(self.hwid)
        if self.port is None:
            msg = "Load cell not found"
            self.log.critical(msg)
            raise RuntimeError(msg)
        if self.is_open:
            self.close()
        self.open()

        self.loadcell_stop()
        self.receiveAll()

        self.log.debug("Connected to '%s'", self.port)
        self.log.debug("%s", self.set_sample_frequency(int(self.freq)))
        self.log.info("Connected to loadcell")

        atexit.register(self.close)

    def start(self):
        """
        Starts the loadcell collecting data
        """
        if not self.thread.is_alive():
            self.running = True

            self.flushInput()

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
        try:
            self.loadcell_pause()
        except serial.SerialException:
            pass

        if self.running:
            self.running = False
            self.thread.join()
            self.thread = threading.Thread(target=self.loop)

        self.receiveAll()

        self.log.info("Loadcell paused")

    def stop(self):
        """
        Stops the loadcell and loadcell thread. Saves data to file
        """
        try:
            self.loadcell_stop()
        except serial.SerialException:
            pass

        if self.running:
            self.running = False
            self.thread.join()
            self.thread = threading.Thread(target=self.loop)

        self.receiveAll()

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

    def loop(self):
        """
        Threading loop
        """
        front_end_counter = 0
        front_end_array = []
        while self.running:
            try:
                index = int.from_bytes(
                    self.receive_bytes(4), byteorder="little", signed=False
                )
                milliseconds = int.from_bytes(
                    self.receive_bytes(4), byteorder="little", signed=False
                )
                data = int.from_bytes(
                    self.receive_bytes(2), byteorder="little", signed=False
                )
                time = self.start_time + datetime.timedelta(
                    milliseconds=float(milliseconds)
                )
                force = self.adc_to_force(data)

                if self.log_file is not None:
                    sys_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    loadcell_time = time.strftime("%Y-%m-%d %H:%M:%S.%f")
                    async_file_hander.write(
                        self.log_file,
                        f"{sys_time},{loadcell_time},{index},{data},{force}\n",
                    )

                front_end_counter += 1
                front_end_array.append(force)
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
            except serial.SerialException:
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
        try:
            self.send("p", recieve=False)
        except serial.SerialException:
            pass
        return

    def loadcell_stop(self):
        """
        Stop sampling
        """
        try:
            self.send("e", recieve=False)
        except serial.SerialException:
            pass
        return

    def set_sample_frequency(self, freq_hz):
        """
        Set the sampling frequency to freq_hz (in hz)
        """
        self.log.debug("Frequency set to '%s'", freq_hz)
        return self.send("f {}".format(freq_hz)), freq_hz

    def send(self, cmd, recieve=True):
        """
        Sends serial command to the loadcell device
        """
        self.log.debug("Sent: '%s'", cmd)
        self.write(bytes(cmd + "\n", encoding="ascii"))  # write to serial tx buffer
        if recieve:
            response = self.receive()
            self.log.debug("Response: '%s'", response)
            return response  # return the response to the command
        return

    def receive(self):
        """
        Sends serial response from the loadcell device
        """
        response = b""
        response += self.readline()  # wait for the first line to fill in the rx buffer
        return (
            response.decode().rstrip()
        )  # return decoded byte response (as string) without traililng newline

    def receive_bytes(self, number_of_bytes):
        """
        Sends a number of bytes from the loadcell device
        """
        return self.read(number_of_bytes)

    def receiveAll(self):
        self.read()
        while self.in_waiting:
            self.read()
        return
