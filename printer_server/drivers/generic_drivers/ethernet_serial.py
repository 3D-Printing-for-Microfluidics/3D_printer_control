import sys
import time
import atexit
import socket
import logging
import threading

class EthernetSerial():
    def __init__(self, name, host=None, port=None, line_ending='\r', timeout=10, logger=logging.getLogger(__name__)):
        super().__init__()
        self.log = logger
        self.name = name
        self.host = host
        self.port = port
        self.line_ending = line_ending
        self.timeout = timeout
        self.socket = None
        self.connected = None
        self.sendLock = threading.Lock()

    def connect(self):
        """Find the device and connect to it."""
        if self.connected is None:
            self.connected = False
            self.log.info("Connecting to %s (%s:%s), this may take up to 1 minute...", self.name, self.host, self.port)

            attempts=10
            wait_between=1
            i = 0
            while i < attempts:  # try up to attempts number of times to create a connection
                i += 1
                try:
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    # initial timeout is 10 sec
                    self.socket.settimeout(10)
                    self.socket.connect((self.host, self.port))
                    self.socket.settimeout(self.timeout)
                    self.connected = True
                    break
                except (OSError, socket.timeout) as ex:
                    if "timed out" in str(ex):
                        break
                    self.log.info("%s. Retrying in %s second(s)", ex, wait_between)
                    self.socket = None  # get rid of handle to bad socket
                    time.sleep(wait_between)  # wait to try again
            if not self.connected:
                self.connected = None
                msg = f"{self.name} not found!"
                self.log.error(msg)
                return False
            
            atexit.register(self.disconnect)
            self.log.info("Connected to %s", self.name)
            return True
        else:
            while self.connected is False:
                time.sleep(0.1)
        return None

    def disconnect(self):
        """Disconnect form the device."""
        if self.connected is not None and self.connected and self.socket is not None:
            self.connected = None
            self.log.info("Disconnecting from %s...", self.name)
            with self.sendLock:
                try:
                    self.socket.close()
                except:
                    self.log.info("Unable to disconnect from %s", self.name)
                    return
            self.socket = None
            self.log.info("Disconnected from %s", self.name)
            

    def send(self, command, notify=True):
        """Send a command to the device.
        """
        with self.sendLock:
            if notify:
                self.log.debug("Sent : '%s'", command)
            command += self.line_ending
            encoded_message = command.encode()
            try:
                self.socket.sendall(encoded_message)
            except socket.timeout:
                msg = "Message send timed out!"
                self.log.critical(msg)
                self.shutdown(is_critical = True)
                sys.exit(msg)
            except Exception as ex:
                self.log.error("Failed to send packet: %s", ex)
                return None

            try:
                rsp = self.socket.recv(1024).decode()
                if notify:
                    self.log.debug("Reply: '%s'", rsp)
                return rsp
            except socket.timeout:
                msg = "Message recieve timed out!"
                self.log.critical(msg)
                self.shutdown(is_critical = True)
                sys.exit(msg)
            except Exception as ex:
                self.log.error("Failed to receive packet: %s", ex)
            return None