import logging
from threading import Lock
from printer_server.drivers.generic_drivers import USBSerial

class MKSTeensy(USBSerial):
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__(vid=config_dict["teensy_vendor_id"], pid=config_dict["teensy_product_id"], sn=config_dict["teensy_serial_number"],  baudrate=config_dict["teensy_baudrate"], logger=self.log)

        self.sendLock = Lock()
            
    def switch_relay(self, relay_num, state):
        if state:
            return self.send(f"H{relay_num}")
        else:
            return self.send(f"L{relay_num}")

    def get_all_relay_status(self):
        while True:
            try:
                l = list(self.send("R"))
                if len(l) < 5:
                    continue
                return l
            except:
                continue

    def get_all_sensor_status(self):
        while True:
            try:
                l = list(self.send("S"))
                if len(l) < 5:
                    continue
                return l
            except:
                continue
    
    def get_crane_position(self):
        while True:
            try:
                p = float(self.send("P"))
                return p
            except:
                continue 
    
    def move_crane(self, mm, relative=False):
        if relative:
            return self.send(f"MR{mm}")
        else:
            return self.send(f"MA{mm}")
        
    def move_crane_top(self):
        return self.send("MT")
        
    def move_crane_bottom(self):
         return self.send("MB")