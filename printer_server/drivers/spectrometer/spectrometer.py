import atexit
import logging
import numpy as np
import seabreeze.spectrometers as sb

class Spectrometer:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.config_dict = config_dict
        self.spectrometer = None
        self.connected = None

    def connect(self, shutdown):
        self.log.debug("Available Spectrometers:")
        for s in sb.list_devices():
            self.log.debug("\t%s", s)

        try:
            if self.config_dict.get("serial num", None) and self.config_dict["serial num"] != "":
                self.spectrometer = sb.Spectrometer.from_serial_number(self.config_dict["serial num"])
            else:
                self.spectrometer = sb.Spectrometer.from_first_available()
            if self.spectrometer is None:
                self.connected = False
            else:
                atexit.register(self.disconnect)
                self.connected = True
        except:
            self.connected = False
        

    def disconnect(self):
        if self.connected:
            self.spectrometer.close()
            self.spectrometer = None
        

    def set_integration_time(self, time=None):
        # Set integration time in ms
        # if time is None, measure max intensity and set integration time to
        # use full range of ADC

        if time is not None:
            if float(time)*1000 < self.spectrometer.integration_time_micros_limits[0] or float(time)*1000 > self.spectrometer.integration_time_micros_limits[1]:
                self.spectrometer.integration_time_micros(float(time)*1000)
        else:
            i_time = 100000
            self.spectrometer.integration_time_micros(i_time)
            max_intensity = self.spectrometer.max_intensity

            while(max_intensity > 6000):
                i_time = i_time/2
                self.spectrometer.integration_time_micros(i_time)
                max_intensity = self.spectrometer.max_intensity

            for _ in range(2):
                max_intensity = self.spectrometer.max_intensity
                i_time = i_time * 60000/max_intensity            
                self.spectrometer.integration_time_micros(i_time)


    def get_integration_limits(self):
        return self.spectrometer.integration_time_micros_limits
    

    def get_max_intensity(self):
        return self.spectrometer.max_intensity
    

    def get_spectrum(self, num_averages=1):
        if num_averages == 1:
            return self.spectrometer.spectrum()
        else:
            spectrums = []
            for _ in range(num_averages):
                spectrums.append(self.spectrometer.spectrum())

            return np.mean( np.array(spectrums), axis=0 )