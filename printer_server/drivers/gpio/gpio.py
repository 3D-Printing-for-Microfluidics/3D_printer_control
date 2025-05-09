import atexit
import logging
from gpiozero.pins.lgpio import LGPIOFactory
from gpiozero import Device, DigitalOutputDevice, DigitalInputDevice, Button

class GPIO:
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.connected = False
        self.config_dict = config_dict
        self.shutdown_func = None
        
        if "film_pin" in config_dict.keys():
            self.film_relay = False
            self.film_relay_pin = config_dict["film_pin"]
            self.film_relay_state = None

        if "wintech_fan_pin1" in config_dict.keys():
            self.wintech_fan_relay = False
            self.wintech_fan_relay_pin1 = config_dict["wintech_fan_pin1"]
            self.wintech_fan_relay_pin2 = config_dict["wintech_fan_pin2"]
            self.wintech_fan_relay_state = None

        if "power_status_pin" in config_dict.keys():
            self.power_status = False
            self.power_status_pin = config_dict["power_status_pin"]

    def initialize(self, shutdown):
        if not self.connected:
            self.log.info("Initializing GPIO...")
            Device.pin_factory = LGPIOFactory(chip=4)

            if "film_pin" in self.config_dict.keys():
                self.film_relay = True
                self.film_device = DigitalOutputDevice(self.film_relay_pin, active_high=True, initial_value=False)

            if "wintech_fan_pin1" in self.config_dict.keys():
                self.wintech_fan_relay = False
                self.wintech_fan_device1 = DigitalOutputDevice(self.wintech_fan_relay_pin1, active_high=True, initial_value=False)
                self.wintech_fan_device2 = DigitalOutputDevice(self.wintech_fan_relay_pin2, active_high=True, initial_value=False)

            if "power_status_pin" in self.config_dict.keys():
                self.shutdown_func = shutdown
                self.power_status = True
                self.power_status_device = DigitalInputDevice(self.power_status_pin, pull_up=None, active_state=False)
                self.power_status_device.when_activated = self.shutdown

            self.connected = True
            atexit.register(self.disconnect)
            self.log.info("Initialized GPIO")

    def shutdown(self):
        self.log.info("System powered off. Shutting down...")
        self.shutdown_func()

    def disconnect(self):
        if self.connected:
            if "film_pin" in self.config_dict.keys() and self.film_relay:
                try:
                    self.film_relay_off()
                    self.film_device.close()
                except:
                    pass
            if "wintech_fan_pin1" in self.config_dict.keys() and self.wintech_fan_relay:
                try:
                    self.wintech_fan_relay_off()
                    self.wintech_fan_device1.close()
                    self.wintech_fan_device2.close()
                except:
                    pass
            if "power_status_pin" in self.config_dict.keys() and self.power_status:
                try:
                    self.power_status_device.close()
                except:
                    pass
            self.connected = False

    def film_relay_on(self):
        self.film_relay_state = True
        self.film_device.on()
        self.log.info("Film relay on")

    def film_relay_off(self):
        self.film_relay_state = False
        self.film_device.off()
        self.log.info("Film relay off")

    def wintech_fan_relay_on(self):
        self.wintech_fan_relay_state = True
        self.wintech_fan_device1.on()
        self.wintech_fan_device2.on()
        self.log.info("Wintech fans off")

    def wintech_fan_relay_off(self):
        self.wintech_fan_relay_state = False
        self.wintech_fan_device1.off()
        self.wintech_fan_device2.off()
        self.log.info("Wintech fans on")
