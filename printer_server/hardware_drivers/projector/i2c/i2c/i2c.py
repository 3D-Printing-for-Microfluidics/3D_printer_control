import io
import atexit
import threading
from fcntl import ioctl

I2C_SLAVE = 0x0703


class I2C:
    """A basic i2c object with simple read and write methods."""

    def __init__(self, address, bus=1):
        """Instantiate new i2c object.

        device (int): device address
        bus (int): bus number
        """
        self.address = address
        self.lock = threading.Lock()
        self.fd = io.open("/dev/i2c-{}".format(bus), "rb+", buffering=0)
        ioctl(self.fd, I2C_SLAVE, address)
        atexit.register(self.fd.close)

    def write(self, data):
        """Write raw byte data to the i2c device."""
        with self.lock:
            self.fd.write(data)

    def read(self, num):
        """Return num bytes, read from the i2c device."""
        with self.lock:
            return self.fd.read(num)
