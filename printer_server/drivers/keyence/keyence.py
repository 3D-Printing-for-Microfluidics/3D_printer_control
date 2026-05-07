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

        super().__init__("CL-3000", host=config_dict["address"], port=config_dict["port"], timeout=1, logger=self.log)
        self.config_dict = config_dict

    def read_all(self):
        data = self.send("MA,0").split(",")[1:]
        return data
    
    def read_sensor_at_index(self, index):
        return float(self.read_all()[index]) # not inverted

    def read_sensor(self, sensor):
        invert = 1
        if self.config_dict["sensors"][sensor]["invert_sign"]:
            invert = -1
        return invert * float(self.read_all()[
            self.config_dict["sensors"][sensor]["measurement_index"]
        ])