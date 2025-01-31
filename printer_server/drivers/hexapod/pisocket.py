import time
import atexit
import socket
import logging
import threading
import socket


from pipython import GCSError, gcserror
from pipython import GCSDevice, pitools
from pipython.interfaces.pigateway import PIGateway, PI_CONTROLLER_CODEPAGE

__signature__ = 0x59c603b46cab28bc52a1b9e4d21ed900

class PISocket(PIGateway):
    """Provide a socket, can be used as context manager."""

    def __init__(self, name, host='localhost', port=50000, timeout=1000, logger=logging.getLogger(__name__)):
        """Provide a connected socket.
        @param host : IP address as string, defaults to "localhost".
        @param port : IP port to use as integer, defaults to 50000.
        @param autoconnect : automaticly connect to controller if True (default)
        """
        self.log = logger
        self.log.debug('create an instance of PISocket(host=%s, port=%s)', host, port)
        self._name = name
        self._timeout = timeout  # milliseconds
        self._host = host
        self._port = port
        self._connected = False
        self._socket = None
        self.sendLock = threading.Lock()

    def connect(self):
        """Find the device and connect to it."""
        if not self._connected:
            self.log.info("Connecting to %s (%s:%s), this may take up to 1 minute...", self._name, self._host, self._port)

            attempts=10
            timeout=1
            i = 0
            while i < attempts:  # try up to attempts number of times to create a connection
                i += 1
                try:
                    self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._socket.settimeout(self._timeout)
                    self._socket.connect((self._host, self._port))
                    self._socket.setblocking(0)
                    self._socket.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)  # disable Nagle algorithm
                    self._connected = True
                    self.flush()
                    self.call_connection_status_changed_callback(self)
                    break
                except (OSError, socket.timeout) as ex:
                    if "timed out" in str(ex):
                        break
                    self.log.info("%s. Retrying in %s second(s)", ex, timeout)
                    self._socket = None  # get rid of handle to bad socket
                    time.sleep(timeout)  # wait to try again
            if not self._connected:
                self._connected = False
                msg = f"{self._name} not found!"
                self.log.error(msg)
                return False
            
            atexit.register(self.disconnect)
            self.log.info("Connected to %s", self._name)
            return True
        return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def __str__(self):
        return 'PISocket(host=%s, port=%s)' % (self._host, self._port)

    @property
    def timeout(self):
        """Return timeout in milliseconds."""
        return self._timeout

    def settimeout(self, value):
        """Set timeout to 'value' in milliseconds."""
        self._timeout = value

    @property
    def connected(self):
        """Return True if a device is connected."""
        return self._connected

    @property
    def connectionid(self):
        """Return 0 as ID of current connection."""
        return 0
    
    def send(self, msg):
        """Send 'msg' to the socket.
        @param msg : String to send.
        """
        self.log.debug('PISocket.send: %r', msg)
        if self._socket.send(msg.encode(PI_CONTROLLER_CODEPAGE)) != len(msg):
            raise GCSError(gcserror.E_2_SEND_ERROR)

    def read(self):
        """Return the answer to a GCS query command.
        @return : Answer as string.
        """
        try:
            received = self._socket.recv(2048)
            self.log.debug('PISocket.read: %r', received)
        except IOError:
            return u''
        return received.decode(encoding=PI_CONTROLLER_CODEPAGE, errors='ignore')
    
    def waitontarget(self, pidevice, axes=None, timeout=300, predelay=0, postdelay=0, polldelay=0.05):
        """Wait until all closedloop 'axes' are on target.
        @param axes : Axes to wait for as string or list/tuple, or None to wait for all axes.
        @param timeout : Timeout in seconds as float.
        @param predelay : Time in seconds as float until querying any state from controller.
        @param postdelay : Additional delay time in seconds as float after reaching desired state.
        @param polldelay : Delay time between polls in seconds as float.
        """
        with self.sendLock:
            axes = pitools.getaxeslist(pidevice, axes)
            if not axes:
                return

        # waitonready
        time.sleep(predelay)
        with self.sendLock:
            if not pidevice.HasIsControllerReady():
                return
            maxtime = time.monotonic() + timeout
            ready = pidevice.IsControllerReady()
        while not ready:
            if time.monotonic() > maxtime:
                raise SystemError('waitonready() timed out after %.1f seconds' % timeout)
            time.sleep(polldelay)
            with self.sendLock:
                ready = pidevice.IsControllerReady()
        with self.sendLock:
            pidevice.checkerror()


        # waitontarget
        with self.sendLock:
            if not pidevice.HasqONT():
                return
        
        with self.sendLock:
            servo = pitools.getservo(pidevice, axes)
            axes = [x for x in axes if servo[x]]
            maxtime = time.monotonic() + timeout
            ontarget = pitools.ontarget(pidevice, axes)
        while not all(list(ontarget.values())):
        # while not all(list(pitools._get_closed_loop_on_target(axes, throwonaxiserror=True).values())):
            if time.monotonic() > maxtime:
                raise SystemError('waitontarget() timed out after %.1f seconds' % timeout)
            time.sleep(polldelay)
            with self.sendLock:
                ontarget = pitools.ontarget(pidevice, axes)
        time.sleep(postdelay)

    def flush(self):
        """Flush input buffer."""
        self.log.debug('PISocket.flush()')
        while True:
            try:
                self._socket.recv(2048)
            except IOError:
                break

    def unload(self):
        self.disconnect()

    def disconnect(self):
        """Disconnect form the device."""
        if self._connected is not None and self._connected and self._socket is not None:
            self._connected = None
            try:
                self.log.info("Disconnecting from %s...", self._name)
                with self.sendLock:
                    self._socket.shutdown(socket.SHUT_RDWR)
                    self._socket.close()
                    self.call_connection_status_changed_callback(self)
                self._socket = None
                self.log.info("Disconnected from %s", self._name)
            except:
                self.log.info("Unexpected error on disconnect")