"""
Keyence Confocal Displacement Sensor
====================================
"""
import logging
from printer_server.drivers.generic_drivers import EthernetSerial

class Keyence(EthernetSerial):
    def __init__(
        self,
        config_dict=None,
        log_level=logging.INFO,
    ):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__(host=config_dict["address"], port=config_dict["port"], timeout=5, logger=self.log)

    def read_all(self):
        data = self.send("MA,0").split(",")[1:]
        return data

    def read_sensor(self, index):
        """Returns the readout of the given sensor in um"""
        return float(self.read_all()[index])