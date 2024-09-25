import logging
from threading import Lock
from printer_server.drivers.generic_drivers import USBSerial

class MKSTeensy(USBSerial):
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__("MKSTeensy", vid=config_dict["teensy_vendor_id"], pid=config_dict["teensy_product_id"], sn=config_dict["teensy_serial_number"], baudrate=config_dict["teensy_baudrate"], multiline=True, logger=self.log)

        self.config_dict = config_dict

        self.relay_requests = []
        for _ in config_dict["teensy relays"]:
            self.relay_requests.append(0)

    def disconnect(self):
        if self.connected:
            self.log.info("Clearing relays")
            try:
                for i in range(len(self.config_dict["teensy relays"])):
                    self.switch_relay(i, False, force=True)
            except:
                pass
        super().disconnect()
            
    def switch_relay(self, relay_num, state, force=False):
        # self.log.info("Set relay %s to %s", relay_num, state)
        if force:
            self.relay_requests[relay_num] = 0
        if state:
            self.relay_requests[relay_num] += 1
        else:
            if self.relay_requests[relay_num] > 0:
                self.relay_requests[relay_num] -= 1
            
        if self.relay_requests[relay_num] > 0:
            return self.send(f"H{relay_num}")
        else:
            return self.send(f"L{relay_num}")

    def get_all_relay_status(self):
        return list(self.send("R"))

    # def get_all_sensor_status(self):
        # return list(self.send("S"))
    
    def get_crane_lower_limit(self):
        return float(self.send("PL"))
    
    def get_crane_upper_limit(self):
        return float(self.send("PU"))
    
    def get_crane_position(self):
        return float(self.send("PP"))
    
    def get_crane_position(self):
        return float(self.send("PP"))
    
    def move_crane(self, mm, relative=False):
        self.log.info("Move crane to %s", mm)
        if relative:
            return self.send(f"MR{mm}")
        else:
            return self.send(f"MA{mm}")
        
    def move_crane_top(self):
        self.log.info("Move crane to top")
        return self.send("MT")
        
    def move_crane_bottom(self):
         self.log.info("Move crane to bottom")
         return self.send("MB")