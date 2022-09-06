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
        if "galil" in config_dict.keys():
            from printer_server.drivers.galil import Galil, Galil_dummy

            if config_dict["galil"]["dummy"]:
                self.galil = Galil_dummy(config_dict=config_dict["galil"])
            else:
                self.galil = Galil(
                    config_dict=config_dict["galil"], log_level=default_log_level
                )

        if "kdc101" in config_dict.keys():
            from printer_server.drivers.kdc101 import KDC101, KDC101_dummy

            if config_dict["kdc101"]["dummy"]:
                self.kdc = KDC101_dummy()
            else:
                self.kdc = KDC101(log_level=default_log_level)

        if "gpio" in config_dict.keys():
            from printer_server.drivers.gpio import GPIO, GPIO_dummy

            if config_dict["gpio"]["dummy"]:
                self.gpio = GPIO_dummy()
            else:
                self.gpio = GPIO(config_dict=config_dict["gpio"])

        if "loadcell" in config_dict.keys():
            from printer_server.drivers.loadcell import LoadCell, Loadcell_dummy

            if config_dict["loadcell"]["dummy"]:
                self.loadcell = Loadcell_dummy()
            else:
                self.loadcell = LoadCell(
                    config_dict=config_dict["loadcell"],
                    log_level=default_log_level,
                )

        if "screen" in config_dict.keys():
            from printer_server.drivers.screen import ScreenThread

            resolutions = []
            for light_engine in config_dict["screen"]["light_engines"]:
                resolution = config_dict[light_engine]["resolution"]
                resolutions.append(tuple(resolution))
            resolutions.append(None)

            self.screen = ScreenThread(
                resolutions=tuple(resolutions),
                config_dict=config_dict["screen"],
                log_level=default_log_level,
            )

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
                self.visitech = Visitech(log_level=default_log_level)

        if "wintech" in config_dict.keys():
            from printer_server.drivers.wintech import Wintech, Wintech_dummy

            if config_dict["wintech"]["dummy"]:
                self.wintech = Wintech_dummy()
            else:
                self.wintech = Wintech(log_level=default_log_level)

        if "keyence" in config_dict.keys():
            from printer_server.drivers.keyence import Keyence

            self.keyence = Keyence()


driver_handles = Printer3D()
