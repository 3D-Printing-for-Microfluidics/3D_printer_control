"""
Keyence Confocal Displacement Sensor
====================================
"""

import logging
import json
import atexit
import socket

DEFAULT_HOST = "192.168.0.15"
DEFAULT_PORT = 24685

READ_ALL_VALUES = "MA,0"

class Keyence:
    """
    Keyence Confocal Displacement Sensor
    """

    def __init__(
        self,
        sensor_ip=DEFAULT_HOST,
        port=DEFAULT_PORT,
        log_level=logging.INFO,
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)


        self.connected = False
        self.sensor_socket = None
        self.host = sensor_ip
        self.port = port
        
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
        data = self.send_command(READ_ALL_VALUES).split(",")
        return data

    def read_sensor(self, index):
        """Returns the readout of the given sensor in um"""
        return float(self.read_all()[index + 1])


def testing1():
    """
    User defined commands executed sequentially as user enters them in the console
    """
    my_keyence1 = Keyence()
    message = input('Enter a message to send to the sensor (press "x" to stop): ')
    while message != "x":
        my_keyence1.send_command(message)
        message = input('Enter a message to send to the sensor (press "x" to stop): ')
    my_keyence1.disconnect()


def testing2():
    """
    Predefined list of commands to send to the sensor and capture data collected at relatively the same and make useful comparisons
    """
    my_keyence2 = Keyence()
    command_list = [
        "MA,0",
        "MA,1",
        "MA,2",
        "MA,3",
        "MA,4",
        "MA,5",
        "MA,6",
        "MA,7",
        "MA,8",
    ]
    for command in command_list:
        my_keyence2.send_command(command)
    my_keyence2.disconnect()


def testing3():
    my_keyence3 = Keyence()
    my_keyence3.read_raw_data()


if __name__ == "__main__":
    # testing1()
    testing2()
    # testing3()
