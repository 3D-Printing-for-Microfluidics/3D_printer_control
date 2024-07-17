import time
import logging

from printer_server.threading_wrapper import Thread
from printer_server.printer_control.print_control import PrintControl
from printer_server.hardware_configuration import driver_handles, config_dict

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class VacuumControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.mks = driver_handles.mks
        self.mks_teensy = driver_handles.mks_teensy

    def connect_hardware(self):
        mks_thread = Thread(log, name="mks_connect_thread", target=self.mks.connect, args=[])
        mks_teensy_thread = Thread(log, name="mks_teensy_thread", target=self.mks_teensy.connect, args=[])
        mks_thread.start()
        mks_teensy_thread.start()
        super().connect_hardware()
        mks_thread.join()
        mks_teensy_thread.join()

    def initialize_hardware(self):
        mks_thread = Thread(log, name="mks_init_thread", target=self.mks.initialize, args=[])
        mks_thread.start()
        super().initialize_hardware()
        mks_thread.join()

    def degass(self):
        degass_thread = Thread(log, name="degass_thread", target=self._degass, args=[])
        degass_thread.start()

    def _degass(self):
        set_pressures = [50, 10, 1, 0.2]
        waits = [60, 60, 60, 60]
        hysteresis = [101, 11, 2, 0.3]
        relay_num = config_dict["mks"]["relays"]["vacuum_pump"]["relay_num"]

        self.mks.set_relay_mode(relay_num, "SET")
        self.mks_teensy.activate_relay(config_dict["mks"]["teensy relays"].index("valve_vacuum"))
        for p, w, h in zip(set_pressures, waits, hysteresis):
            while(self.mks.pressures[1] > p):
                self.mks_teensy.activate_relay(config_dict["mks"]["teensy relays"].index("valve_pump2"))
                time.sleep(0.1)
            self.mks_teensy.deactivate_relay(config_dict["mks"]["teensy relays"].index("valve_pump2"))
            time.sleep(w)
        self.mks_teensy.activate_relay(config_dict["mks"]["teensy relays"].index("valve_vent2"))
        self.mks_teensy.deactivate_relay(config_dict["mks"]["teensy relays"].index("valve_vacuum"))
        self.mks.set_relay_mode(relay_num, "CLEAR")
