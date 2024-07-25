import datetime
import logging
import serial
import atexit
import serial.tools.list_ports
import serial.serialutil
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander


class Accelerometer(serial.Serial):

    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        """
        Initializes the accelerometer
        """
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.config_dict = config_dict

        super().__init__(baudrate=115200, timeout=1)
        self.port = None  # start with no port
        # self.status = None              # status to be updated after every send

        self.connected = False

        self.thread = Thread(self.log, name="accelerometer_loop_thread", target=self.loop)
        self.running = False

        # self.connect()
        # self.running = True
        # self.thread.start()

        # input()

        # self.running = False
        # self.thread.join()

    def connect(self):
        """
        Connects to the accelerometer and sets parameters.
        """
        self.port = self.findUsbPort(self.config_dict["hwid"])
        if self.port is None:
            return False
        if self.is_open:
            self.close()
        self.open()
        self.receiveAll()
        self.set_sample_period(self.config_dict["measurement_period_ms"])
        self.log.info("Connected to Accelerometer")
        self.connected = True
        atexit.register(self.disconnect)
        return True

    def disconnect(self):
        if self.connected:
            self.close()
            self.connected = False
            self.log.info("Disconnected from Accelerometer")

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

    def start(self):
        """
        Starts the accelerometer collecting data
        """
        if not self.thread.is_alive():
            self.running = True

            self.flushInput()

            self.log.info("Accelerometer started")
            temp = self.accel_start()
            if self.start_time == 0:
                accel_time = temp.split("'")
                accel_time = float(accel_time[1])
                self.start_time = datetime.datetime.now() - datetime.timedelta(
                    milliseconds=accel_time
                )
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
        try:
            self.accel_pause()
        except serial.SerialException:
            pass

        if self.running:
            self.running = False
            self.thread.join()
            self.thread = Thread(self.log, name="accelerometer_loop_thread", target=self.loop)

        self.receiveAll()

        self.log.info("Accelerometer paused")

    def stop(self):
        """
        Stops the accelerometer and accelerometer thread. Saves data to file
        """
        try:
            self.accel_stop()
        except serial.SerialException:
            pass

        if self.running:
            self.running = False
            self.thread.join()
            self.thread = Thread(self.log, name="accelerometer_loop_thread", target=self.loop)

        self.receiveAll()

        self.log.info("Accelerometer stopped")
        self.start_time = 0

    def loop(self):
        """
        Threading loop
        """
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
                ret = self.receive_bytes(1)
                while ret != b'\n':
                    ret = self.receive_bytes(1)
                accel = data/16384

                if self.log_file is not None:
                    sys_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    accel_time = time.strftime("%Y-%m-%d %H:%M:%S.%f")
                    async_file_hander.write(
                        self.log_file,
                        f"{sys_time},{accel_time},{index},{data}\n",
                    )

                self.currentAccel = accel
                self.currentIndex = index
            except serial.SerialException:
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
        try:
            self.send("p", recieve=False)
        except serial.SerialException:
            pass
        return

    def accel_stop(self):
        """
        Stop sampling
        """
        try:
            self.send("e", recieve=False)
        except serial.SerialException:
            pass
        return

    def set_sample_period(self, ms):
        """
        Set the sampling period to ms (in ms)
        """
        self.log.debug("Period set to '%s'", ms)
        return self.send("t {}".format(ms)), ms

    def send(self, cmd, recieve=True):
        """
        Sends serial command to the accelerometer device
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
        Sends serial response from the accelerometer device
        """
        response = b""
        response += self.readline()  # wait for the first line to fill in the rx buffer
        return (
            response.decode().rstrip()
        )  # return decoded byte response (as string) without traililng newline

    def receive_bytes(self, number_of_bytes):
        """
        Sends a number of bytes from the accelerometer device
        """
        return self.read(number_of_bytes)

    def receiveAll(self):
        self.read()
        while self.in_waiting:
            self.read()
        return
