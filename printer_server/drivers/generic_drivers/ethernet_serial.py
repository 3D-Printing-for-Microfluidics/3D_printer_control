import sys
import time
import atexit
import socket
import logging
import threading

class EthernetSerial():
    def __init__(self, host=None, port=None, line_ending='\r', logger=logging.getLogger(__name__)):
        self.log = logger
        self.host = host
        self.port = port
        self.line_ending = line_ending
        self.socket = None
        self.connected = None
        self.sendLock = threading.Lock()

    def connect(self, shutdown):
        """Find the device and connect to it."""
        if self.connected is None:
            self.connected = False
            self.log.info("Connecting to device (%s), this may take up to 1 minute...", self.host)

            attempts=10
            timeout=1
            i = 0
            while i < attempts:  # try up to attempts number of times to create a connection
                i += 1
                try:
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.socket.settimeout(10)
                    self.socket.connect((self.host, self.port))
                    self.connected = True
                    self.shutdown = shutdown
                except (OSError, socket.timeout) as e:
                    if "timed out" in str(e):
                        break
                    self.log.info("%s. Retrying in %s second(s)", e, timeout)
                    self.socket = None  # get rid of handle to bad socket
                    time.sleep(timeout)  # wait to try again
            if not self.connected:
                self.connected = None
                msg = f"Device not found!"
                self.log.critical(msg)
                return False
            
            atexit.register(self.disconnect)
            self.log.info("Connected to device")
            return True
        else:
            while self.connected is False:
                time.sleep(0.1)
        return None

    def disconnect(self):
        """Disconnect form the device."""
        if self.connected is not None and self.connected and self.socket is not None:
            self.connected = None
            try:
                with self.sendLock:
                    self.socket.close()
                self.socket = None
                self.log.info("Disconnected from device")
            except:
                self.log.error("Unexpected error on disconnect")

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
            except Exception as e:
                self.log.error("Failed to receive packet: %s", e)
            return None