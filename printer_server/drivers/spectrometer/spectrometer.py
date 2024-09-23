import time
import atexit
import logging
import numpy as np
import seabreeze.spectrometers as sb
import seabreeze.pyseabreeze as psb

class Spectrometer:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        self.config_dict = config_dict
        self.spectrometer = None
        self.connected = None

    def connect(self):
        self.log.debug("Available Spectrometers:")
        # If we dont list devices using psb, sometimes it cannot find the device
        api = psb.SeaBreezeAPI()
        for s in api.list_devices():
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
        except Exception as ex:
            self.log.error("Failed to connect to Spectrometer (%s)", ex)
            self.connected = False
        

    def disconnect(self):
        if self.connected:
            self.log.info("Disconnected to Spectrometer")
            self.spectrometer = None
        

    def set_integration_time(self, i_time=None):
        # Set integration time in ms
        # if time is None, measure max intensity and set integration time to
        # use full range of ADC

        if i_time is not None:
            self.log.info("Integration time set to %s ms", i_time)
            i_time = float(i_time)*1000
            limits = self.get_integration_limits()
            if i_time >= limits[0] or i_time <= limits[1]:
                self._set_integration_time(i_time)
                return i_time
            return -1
        else:
            self.log.info("Calculating integration time...")
            i_time = self.config_dict["default_integration_time"]*1000
            self._set_integration_time(i_time)
            time.sleep(1)
            intensity = self.get_max_intensity()
            self.log.debug("Integration time: %s Max value: %s", i_time/1000, intensity)

            while(intensity > 65000):
                i_time = i_time/2
                if i_time < self.get_integration_limits()[0]:
                    self._set_integration_time(limits[0])
                    time.sleep(1)
                    intensity = self.get_max_intensity()
                    self.log.debug("Integration time: %s Max value: %s", i_time/1000, intensity)
                    return self.get_integration_limits()[0]/1000
                self._set_integration_time(i_time)
                time.sleep(1)
                intensity = self.get_max_intensity()
                self.log.debug("Integration time: %s Max value: %s", i_time/1000, intensity)

            for _ in range(2):
                i_time = i_time * 65000/intensity        
                if i_time > self.get_integration_limits()[1]:
                    self._set_integration_time(limits[1])
                    time.sleep(1)
                    intensity = self.get_max_intensity()
                    self.log.debug("Integration time: %s Max value: %s", i_time/1000, intensity)
                    return self.get_integration_limits()[1]/1000 
                self._set_integration_time(i_time)
                time.sleep(1)
                intensity = self.get_max_intensity()
                self.log.debug("Integration time: %s Max value: %s", i_time/1000, intensity)
            self.log.info("Integration time set to %s ms", i_time)
            return i_time/1000
        
    def _set_integration_time(self, i_time):
        self.spectrometer.integration_time_micros(i_time)

    def get_integration_limits(self):
        return self.spectrometer.integration_time_micros_limits
    

    def get_max_intensity(self):
        return np.max(self.spectrometer.intensities(correct_dark_counts=True, correct_nonlinearity=True)[25:])
    
    
    def get_absolute_max_intensity(self):
        return self.spectrometer.max_intensity
    

    def get_spectrum(self, num_averages=1):
        self.log.info("Capturing spectra")
        if num_averages == 1:
            return self.spectrometer.spectrum(correct_dark_counts=True, correct_nonlinearity=True)[:, 25:].tolist()
        else:
            spectrums = []
            for _ in range(num_averages):
                spectrums.append(self.spectrometer.spectrum(correct_dark_counts=True, correct_nonlinearity=True)[:, 25:])

            return np.mean( np.array(spectrums), axis=0 ).tolist()