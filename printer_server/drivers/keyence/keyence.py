"""
Keyence Confocal Displacement Sensor
====================================
"""
import logging
import json
import atexit
import socket

class Keyence:
    def __init__(
        self,
        config_dict=None,
        log_level=logging.INFO,
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)


        self.connected = False
        self.sensor_socket = None
        self.host = config_dict["ip_addr"]
        self.port = config_dict["port"]
        
    def connect(self):
        self.connected = False
        try:
            self.sensor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sensor_socket.settimeout(5)
            self.sensor_socket.connect((self.host, self.port))
            self.log.info(
                "Connected to Keyence sensor"
            )
            self.connected = True
            atexit.register(self.disconnect)
        except (OSError, socket.timeout):
            self.log.critical(f"Keyence sensor not found! (CL-3000)")
            return False
        else:
            return True

    def disconnect(self):
        if self.connected and self.sensor_socket is not None:
            self.sensor_socket.close()
            self.connected = False
            self.sensor_socket = None
            self.log.info("Disconnected from Keyence sensor")

    def send_command(self, message):
        message += "\r"
        encoded_message = message.encode()
        try:
            self.sensor_socket.sendall(encoded_message)
        except Exception as ex:
            self.log.error(f"Failed to send message to sensor due to {ex}")
        else:
            self.log.debug(f"Command sent: {message}")
        response = self.sensor_socket.recv(1024).decode()
        self.log.debug(f"Feedback: {response}")
        return response

    def read_all(self):
        data = self.send_command("MA,0").split(",")[1:]
        return data

    def read_sensor(self, index):
        """Returns the readout of the given sensor in um"""
        return float(self.read_all()[index])