import atexit
import serial
import serial.tools.list_ports
import serial.serialutil


def findUsbPort(hwid):
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if hwid.upper() in p.hwid:
            print("Found '{}' at '{}'".format(p.hwid, p.device))
            return p.device
    return None  # not found


# class LoadCell():
class LoadCell(serial.Serial):
    def __init__(self, hwid="16c0:0483", verbose=True):
        super().__init__(baudrate=115200, timeout=1)
        # Button parameters
        self.verbose = verbose
        self.hwid = hwid
        self.port = None  # start with no port
        self.status = None  # status to be updated after every send

        atexit.register(self.close)

    def connect(self):
        self.port = findUsbPort(self.hwid)
        if self.port is None:
            raise ValueError("Load cell not found")
        if self.is_open:
            self.close()
        self.open()
        self.flushInput()
        self.flushOutput()
        print("Connected to", self.port)

    def set_gain(self, value, channel=0):
        """
        Set the gain of the specified channel (0,1) to value (0-255)

        x = 94500 - ((94500 - 280) / 255) * value
        gain = 1 + 49400 / x
        """
        x = 94500 - ((94500 - 280) / 255) * value  # ranges from 0:94500 - 255:280
        g = 1 + 49400 / x  # ranges from 0:1.5227513227513227 - 255:177.42857142857142
        print("gain set to {}", g)
        return self.send("<g,{},{}>".format(channel, value)), g

    def set_filter_corner(self, value, channel=0):
        """
        Set the filter 3d corner of the specified channel (0,1) to value (0-255)

        pi = 3.14159265359
        x = 94500 - ((94500 - 280) / 255) * value
        f_corner = 1 / (2 * pi * x * 0.0000000047) * 2 / 3
        """
        pi = 3.14159265359
        x = 94500 - ((94500 - 280) / 255) * value  # ranges from 0:94500 - 255:280
        f_corner = (
            1 / (2 * pi * x * 0.0000000047) * 2 / 3
        )  # ranges from 0:238.89067971313725 - 255:80625.60440318382
        print("corner set to {}", f_corner)
        return self.send("<f,{},{}>".format(channel, value))

    def set_sample_period(self, period_us, channel=0):
        """
        Set the sampling period of the specified channel (0,1) to period_us (in microseconds)
        """
        print("period set to {}", period_us)
        return self.send("<p,{},{}>".format(channel, period_us))

    def sample(self, num_samples, period_us, channel=0):
        """
        Sample the specified channel (0,1) for num_samples at a period of period_us (in microseconds)
        """
        return self.send("<s,{},{},{}>".format(channel, num_samples, period_us))

    def send(self, cmd):
        if self.verbose:
            print("Sent: " + cmd)
        self.write(bytes(cmd + "\n", encoding="ascii"))  # write to serial tx buffer
        response = self.receive()
        if self.verbose:
            print("Response: ", response)
        return response  # return the response to the command

    def receive(self):
        response = b""
        response += self.readline()  # wait for the first line to fill in the rx buffer
        while self.in_waiting:  # while there is more data in the rx buffer
            response += self.readline()  # read next line from rx buffer
        return (
            response.decode().rstrip()
        )  # return decoded byte response (as string) without traililng newline


if __name__ == "__main__":
    l = LoadCell(verbose=True)
    # print(l.receive())
    l.connect()
    # print(l.in_waiting)
    # print(l.receive())
    # print(l.receive())
    l.set_filter_corner(200)  # 1096 Hz
    # l.set_gain(120)          # gain = 1.98
    # l.set_gain(0)          # gain = 1

    for gain in [0, 10, 50, 100, 150, 200, 250, 255]:
        _, g = l.set_gain(gain)

        # while True:
        #     try:
        result = l.sample(num_samples=100, period_us=1, channel=0)

        import matplotlib.pyplot as plt

        t = []
        s = []

        # parse sample response
        result = [i.split(",") for i in result.splitlines()]
        for i in result:
            if len(i) == 3:
                t.append(int(i[1]) / 1000)  # convert us to ms
                s.append(int(i[2]))

        plt.plot(t, s)
        plt.xlabel("Time (ms)")
        plt.ylabel("Counts")
        plt.title("Gain = {:0.2f} ({} counts)".format(g, gain))
        plt.grid(True)
        plt.savefig("gain_test_{}.png".format(gain))
        plt.show()
        # except KeyboardInterrupt:
        #     exit()
