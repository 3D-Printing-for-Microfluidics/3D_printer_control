"""
Keyence Confocal Displacement Sensor
====================================
"""
import logging
import json
import atexit
import socket
import time

class Keyence:
    def __init__(
        self,
        config_dict=None,
        log_level=logging.INFO,
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)


        self.connected = False
        self.socket = None
        self.host = config_dict["ip_addr"]
        self.port = config_dict["port"]
        
    def connect(self):
        attempts=10
        timeout=1
        self.log.info("Connecting to Keyence sensors, this may take up to 1 minute...")

        # start TCP connection
        i = 0
        self.connected = False
        while i < attempts:  # try up to attempts number of times to create a connection
            i += 1
            try:  # attempt a new connection
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(10)
                self.socket.connect((self.host, self.port))
                self.connected = True
            except (OSError, socket.timeout) as e:
                if "timed out" in str(e):
                    i = attempts
                self.log.info("%s. Retrying in %s second(s)", e, timeout)
                self.socket = None  # get rid of handle to bad socket
                time.sleep(timeout)  # wait to try again
        if not self.connected:  # connection failed every time, notify user
            msg = "Keyence sensor not found! (CL-3000)"
            self.log.critical(msg)
            return False

        # register exit handlers
        atexit.register(self.disconnect)
        self.log.info("Connected to Keyence sensor")
        return True

    def disconnect(self):
        if self.connected and self.socket is not None:
            self.socket.close()
            self.connected = False
            self.socket = None
            self.log.info("Disconnected from Keyence sensor")

    def send_command(self, message):
        message += "\r"
        encoded_message = message.encode()
        try:
            self.socket.sendall(encoded_message)
        except Exception as ex:
            self.log.error(f"Failed to send message to sensor due to {ex}")
        else:
            self.log.debug(f"Command sent: {message}")
        response = self.socket.recv(1024).decode()
        self.log.debug(f"Feedback: {response}")
        return response

    def read_all(self):
        data = self.send_command("MA,0").split(",")[1:]
        return data

    def read_sensor(self, index):
        """Returns the readout of the given sensor in um"""
        return float(self.read_all()[index])