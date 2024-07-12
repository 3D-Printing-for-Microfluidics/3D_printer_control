import json
import logging
from pathlib import Path
from printer_server.settings import Config

default_log_level = logging.INFO
dummy = False


configuration_path = Path(Config.PRINT_SERVER_FOLDER).rglob("hardware_configuration.json")
with open(next(configuration_path), "r") as file_handle:
    config_dict = json.load(file_handle)
config_dict = config_dict[Config.HOSTNAME]


class Printer3D:
    """Provides hardware handles to the Flask print control."""

    def __init__(self):
        # Dynamically import python snippits
        global config_dict
        if "coord_systems" in config_dict.keys():
            from printer_server.drivers.coord_systems import Coord_Systems
            self.coord_systems_control = Coord_Systems()

        if "environmental_sensors" in config_dict:
            from printer_server.drivers.environmental_sensors import EnvironmentalSensors, EnvironmentalSensors_dummy

            if config_dict["environmental_sensors"]["dummy"]:
                self.environmental_sensors = EnvironmentalSensors_dummy()
            else:
                self.environmental_sensors = EnvironmentalSensors(config_dict=config_dict["environmental_sensors"], log_level=default_log_level)

        if "galil" in config_dict.keys():
            from printer_server.drivers.galil import Galil, Galil_dummy

            if config_dict["galil"]["dummy"]:
                self.galil = Galil_dummy(config_dict=config_dict["galil"])
            else:
                self.galil = Galil(
                    config_dict=config_dict["galil"], log_level=default_log_level
                )

        if "gpio" in config_dict.keys():
            from printer_server.drivers.gpio import GPIO, GPIO_dummy

            if config_dict["gpio"]["dummy"]:
                self.gpio = GPIO_dummy()
            else:
                self.gpio = GPIO(config_dict=config_dict["gpio"])


        if "kdc101" in config_dict.keys():
            from printer_server.drivers.kdc101 import KDC101, KDC101_dummy

            if config_dict["kdc101"]["dummy"]:
                self.kdc101 = KDC101_dummy()
            else:
                self.kdc101 = KDC101(config_dict=config_dict["kdc101"], log_level=default_log_level)

        if "keyence" in config_dict.keys():
            from printer_server.drivers.keyence import Keyence, Keyence_dummy

            if config_dict["keyence"]["dummy"]:
                self.keyence = Keyence_dummy(
                    config_dict=config_dict["keyence"], 
                    log_level=default_log_level
                )
            else:
                self.keyence = Keyence(
                    config_dict=config_dict["keyence"], 
                    log_level=default_log_level
                )
        
        if "loadcell" in config_dict.keys():
            from printer_server.drivers.loadcell import LoadCell, Loadcell_dummy

            if config_dict["loadcell"]["dummy"]:
                self.loadcell = Loadcell_dummy()
            else:
                self.loadcell = LoadCell(
                    config_dict=config_dict["loadcell"],
                    log_level=default_log_level,
                )
        
        if "mks" in config_dict.keys():
            from printer_server.drivers.mks import MKS946, MKS946_dummy, MKSTeensy, MKSTeensy_dummy

            if config_dict["mks"]["dummy"]:
                self.mks = MKS946_dummy()
                self.mks_teensy = MKSTeensy_dummy()
            else:
                self.mks = MKS946(
                    config_dict=config_dict["mks"],
                    log_level=default_log_level
                )
                self.mks_teensy = MKSTeensy(
                    config_dict=config_dict["mks"],
                    log_level=default_log_level
                )

        if "photodiode" in config_dict.keys():
            from printer_server.drivers.photodiode import Photodiode, Photodiode_dummy

            if config_dict["photodiode"]["dummy"]:
                self.photodiode = Photodiode_dummy()
            else:
                self.photodiode = Photodiode(config_dict=config_dict["photodiode"], log_level=default_log_level)

        if "screen" in config_dict.keys():
            from printer_server.drivers.screen import ScreenThread

            config_dict["screen"]["light_engines"] = config_dict["light_engines"]

            resolutions = []
            for light_engine in config_dict["light_engines"]:
                resolution = config_dict[light_engine]["resolution"]
                resolutions.append(tuple(resolution))
            resolutions.append(None)

            self.screen = ScreenThread(
                resolutions=tuple(resolutions),
                config_dict=config_dict["screen"],
                log_level=default_log_level,
            )

        if "spectrometer" in config_dict.keys():
            from printer_server.drivers.spectrometer import Spectrometer, Spectrometer_dummy

            if config_dict["spectrometer"]["dummy"]:
                self.spectrometer = Spectrometer_dummy()
            else:
                self.spectrometer = Spectrometer(config_dict=config_dict["spectrometer"], log_level=default_log_level)

        if "tiptilt" in config_dict.keys():
            from printer_server.drivers.tiptilt import TipTilt, TipTilt_dummy

            if config_dict["tiptilt"]["dummy"]:
                self.tiptilt = TipTilt_dummy(verbose=True)
            else:
                self.tiptilt = TipTilt(
                    config_dict=config_dict["tiptilt"],
                    log_level=default_log_level,
                )

        if "visitech" in config_dict.keys():
            from printer_server.drivers.visitech import Visitech, Visitech_dummy

            if config_dict["visitech"]["dummy"]:
                self.visitech = Visitech_dummy()
            else:
                self.visitech = Visitech(
                    config_dict["visitech"]["leds"],
                    log_level=default_log_level,
                    dual_led=config_dict["visitech"]["dual_led"],
                )

        if "wintech" in config_dict.keys():
            from printer_server.drivers.wintech import Wintech, Wintech_dummy

            if config_dict["wintech"]["dummy"]:
                self.wintech = Wintech_dummy()
            else:
                self.wintech = Wintech(log_level=default_log_level)

        self.bp_stage = None
        self.focus_stage = None
        self.xy_stage = None
        self.ttr_stage = None
        self.light_engines = {}

        if "bp" in config_dict["stages"]:
            if hasattr(self, config_dict["stages"]["bp"]):
                self.bp_stage = getattr(self, config_dict["stages"]["bp"])
            else:
                from printer_server.drivers.generic_drivers import BPStageDriver
                self.bp_stage = BPStageDriver()


        if "focus" in config_dict["stages"]:
            if hasattr(self, config_dict["stages"]["focus"]):
                self.focus_stage = getattr(self, config_dict["stages"]["focus"])
            else:
                from printer_server.drivers.generic_drivers import FocusStageDriver
                self.focus_stage = FocusStageDriver()


        if "x_y" in config_dict["stages"]:
            if hasattr(self, config_dict["stages"]["x_y"]):
                self.xy_stage = getattr(self, config_dict["stages"]["x_y"])
            else:
                from printer_server.drivers.generic_drivers import XYStageDriver
                self.xy_stage = XYStageDriver()
   

        if "t_t_r" in config_dict["stages"]:
            if hasattr(self, config_dict["stages"]["t_t_r"]):
                self.ttr_stage = getattr(self, config_dict["stages"]["t_t_r"])
            else:
                from printer_server.drivers.generic_drivers import TTRStageDriver
                self.ttr_stage = TTRStageDriver()
        
        if "light_engines" in config_dict:
            for light_engine in config_dict["light_engines"]:
                if hasattr(self, light_engine):
                    self.light_engines[light_engine] = getattr(self, light_engine)


    def disconnect(self):
        if hasattr(self, "environmental_sensors"):
            self.environmental_sensors.disconnect()
        if hasattr(self, "galil"):
            self.galil.disconnect()
        if hasattr(self, "gpio"):
            self.gpio.disconnect()
        if hasattr(self, "kdc"):
            self.kdc101.disconnect()
        if hasattr(self, "keyence"):
            self.keyence.disconnect()
        if hasattr(self, "loadcell"):
            self.loadcell.disconnect()
        if hasattr(self, "mks"):
            self.mks.disconnect()
            self.mks_teensy.disconnect()
        if hasattr(self, "photodiode"):
            self.photodiode.disconnect()
        if hasattr(self, "screen"):
            self.screen.stop()
        if hasattr(self, "spectrometer"):
            self.spectrometer.disconnect()
        if hasattr(self, "tiptilt"):
            self.tiptilt.disconnect()
        if hasattr(self, "visitech"):
            self.visitech.disconnect()
        if hasattr(self, "wintech"):
            self.wintech.disconnect()
            
driver_handles = Printer3D()
