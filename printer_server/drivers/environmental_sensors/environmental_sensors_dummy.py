from printer_server.logging_handler import dummy_log


class Environmental_sensors_dummy:
    @dummy_log
    def __init__(self, *args, **kwargs):
        pass

    @dummy_log
    def findUsbPort(self, *args, **kwargs):
        pass

    @dummy_log
    def connect(self, *args, **kwargs):
        pass

    @dummy_log
    def disconnect(self, *args, **kwargs):
        pass


    ########################
    # ESP32 serial wrappers
    ########################
            

    def get_all_measurements(self, *args, **kwargs):
        pass

    
    def get_temperature(self, *args, **kwargs):
        pass
    
    def get_humidity(self, *args, **kwargs):
        pass

    def get_pressure(self, *args, **kwargs):
        pass

    def get_gas(self, *args, **kwargs):
        pass

    def get_airQuality(self, *args, **kwargs):
        pass

    def get_voc(self, *args, **kwargs):
        pass



    def send(self, *args, **kwargs):
        pass
    
    def receive(self, *args, **kwargs):
        pass