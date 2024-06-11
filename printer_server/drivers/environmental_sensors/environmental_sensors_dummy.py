from printer_server.logging_handler import dummy_log


class EnvironmentalSensors_dummy:
    @dummy_log
    def __init__(self, *args, **kwargs):
        pass

    @dummy_log
    def findUsbPort(self, *args, **kwargs):
        pass

    @dummy_log
    def connect(self, *args, **kwargs):
        return True

    @dummy_log
    def disconnect(self, *args, **kwargs):
        pass

    @dummy_log
    def set_log_file(self, *args, **kwargs):
        pass

    @dummy_log
    def start(self, *args, **kwargs):
        pass

    @dummy_log
    def stop(self, *args, **kwargs):
        pass

    @dummy_log
    def loop(self, *args, **kwargs):
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