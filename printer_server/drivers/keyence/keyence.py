"""
Keyence Confocal Displacement Sensor
====================================
"""

import logging
import json
import socket

DEFAULT_SENSOR_IP = "192.168.0.15"
DEFAULT_SENSOR_PORT = 24685
LOG_FORMAT = "%(asctime)s: %(levelname)s: %(name)s: %(message)s"

READ_ALL_VALUES = "MA,0"
# READ_ALL_VALUES = "MA,2"


class Keyence:
    """
    Keyence Confocal Displacement Sensor
    """

    def __init__(
        self,
        sensor_ip=DEFAULT_SENSOR_IP,
        sensor_port=DEFAULT_SENSOR_PORT,
        log_level=logging.INFO,
    ):
        self.sensor_socket = None
        self.sensor_address = sensor_ip
        self.sensor_port = sensor_port
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        # ---------------------------------------------------------------------------------
        # formatter = logging.Formatter("%(asctime)s: %(levelname)s: %(name)s: %(message)s")
        # stream_handler = logging.StreamHandler()
        # stream_handler.setFormatter(formatter)
        # self.log.addHandler(stream_handler)
        # ---------------------------------------------------------------------------------

        # self.connected = self.connect()

    def connect(self) -> bool:
        """[summary]

        Returns:
            bool: [description]
        """
        try:
            self.sensor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sensor_socket.connect((self.sensor_address, self.sensor_port))
            # print(f"Connection established @ {self.sensor_address} in port {self.sensor_port}")
            self.log.info(
                f"Connection established @ {self.sensor_address} in port {self.sensor_port}"
            )
        except Exception as ex:
            # print(f"Connection attempt failed due to {ex}")
            self.log.error(f"Connection attempt failed due to {ex}")
            return False
        else:
            return True

    def disconnect(self) -> bool:
        """[summary]

        Returns:
            bool: [description]
        """
        if self.sensor_socket is not None:
            self.sensor_socket.close()
            self.log.info("Keyence sensor disconnected.")
            return True
        return False

    def send_command(self, message: str) -> list:
        """[summary]

        Args:
            message (str): [description]

        Returns:
            list: [description]
        """
        message += "\r"
        encoded_message = message.encode()
        try:
            self.sensor_socket.sendall(encoded_message)
        except Exception as ex:
            # print(f"Failed to send message to sensor due to {ex}")
            self.log.error(f"Failed to send message to sensor due to {ex}")
        else:
            # print(f"Command sent: {message}")
            self.log.debug(f"Command sent: {message}")
        response = self.sensor_socket.recv(1024).decode()
        # print(f"Feedback: {response}")
        self.log.debug(f"Feedback: {response}")
        return response

    def read_all(self):
        data = self.send_command(READ_ALL_VALUES).split(",")
        # print(f"data type: {type(data)}, data: {data}")
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
