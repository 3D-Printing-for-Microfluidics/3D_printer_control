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

    def send(self, cmd, recieve=True):
        """
        Sends serial command to the accelerometer device
        """
        print("Sent: '%s'", cmd)
        self.write(bytes(cmd + "\n", encoding="ascii"))  # write to serial tx buffer
        if recieve:
            response = self.receive()
            print("Response: '%s'", response)
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
        )  # return decoded byte response (as string) without trailing newline

    def receiveAll(self):
        self.read()
        while self.in_waiting:
            self.read()
        return

    def loop(self):
        """
        Threading loop
        """
        self.start_time = -1
        print(self.receive())
        print(self.receive())
        print(self.receive())
        with open("output.csv", "w") as f:
            f.write(
                f"sys_time,accel_time,index,data,force\n",
            )
            while self.running:
                try:
                    index = self.receive()
                    milliseconds = self.receive()
                    if self.start_time == -1:
                        self.start_time = datetime.datetime.now() - datetime.timedelta(
                            milliseconds=float(milliseconds)
                        )
                    data = self.receive()
                    time = self.start_time + datetime.timedelta(
                        milliseconds=float(milliseconds)
                    )

                    sys_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    accel_time = time.strftime("%Y-%m-%d %H:%M:%S.%f")
                    f.write(
                        f"{sys_time},{accel_time},{index},{data}\n",
                    )
                except serial.SerialException:
                    self.running = False
                except ValueError:
                    print("Unable to parse accelerometer data - cast error")
                    continue
                except OverflowError:
                    print("Unable to parse accelerometer data - time overflow")