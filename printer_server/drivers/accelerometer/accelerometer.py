import threading
import datetime
import serial
import serial.tools.list_ports
import serial.serialutil


class Accelerometer(serial.Serial):

    def __init__(self):
        """
        Initializes the accelerometer
        """
        super().__init__(baudrate=115200, timeout=1)
        self.port = None  # start with no port
        # self.status = None              # status to be updated after every send

        self.connected = False

        self.thread = threading.Thread(target=self.loop)

        self.connect()
        self.running = True
        self.thread.start()

        input()

        self.running = False
        self.thread.join()

    def connect(self):
        """
        Connects to the accelerometer and sets parameters.
        """
        self.port = self.findUsbPort("VID:PID=1A86:7523")
        if self.port is None:
            return False
        if self.is_open:
            self.close()
        self.open()
        self.receiveAll()
        self.connected = True
        return True

    def disconnect(self):
        if self.connected:
            self.close()
            self.connected = False
            print("Disconnected from Accelerometer")

    def findUsbPort(self, hwid):
        """
        Finds serial port with given hwid

        Parameters:
            hwid - device identifier
        """
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            print(p.hwid)
            if hwid.upper() in p.hwid:
                print("Found '%s' at '%s'", p.hwid, p.device)
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
            self.thread = Thread(self.log, name="loadcell_loop_thread", target=self.loop)

        self.receiveAll()

        self.log.info("Accelerometer stopped")
        self.start_time = 0

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
                ret = self.receive_bytes(1)
                while ret != b'\n':
                    ret = self.receive_bytes(1)
                accel = data

                if self.log_file is not None:
                    sys_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    loadcell_time = time.strftime("%Y-%m-%d %H:%M:%S.%f")
                    async_file_hander.write(
                        self.log_file,
                        f"{sys_time},{loadcell_time},{index},{data},{force}\n",
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

    def set_sample_frequency(self, freq_hz):
        """
        Set the sampling frequency to freq_hz (in hz)
        """
        self.log.debug("Frequency set to '%s'", freq_hz)
        return self.send("f {}".format(freq_hz)), freq_hz

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
