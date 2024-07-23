import time
import logging

from printer_server.extensions import socketio
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
        self.degass_running = False
        self.degass_thread = None
        self.degass_state = None

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
        self.degass_state = "idle"
        socketio.emit(f"update_degass_state", self.degass_state, namespace="/printing")

    def degass(self, msg):
        if msg == "run":
            self.degass_running = True
            self.degass_thread = Thread(log, name="degass_thread", target=self.run_degass, args=[])
            self.degass_thread.start()
            self.degass_state = "running"
        elif msg == "stop":
            self.degass_running = False
            self.degass_thread.join()
            self.finish_degass()
            self.degass_state = "idle"
        elif msg == "finish":
            self.finish_degass()
            self.degass_state = "idle"
        socketio.emit(f"update_degass_state", self.degass_state, namespace="/printing")

    def run_degass(self):
        set_pressures = [50, 10, 7, 5, 3, 1, 0.9, 0.8, 0.1]
        waits = [30, 30, 30, 30, 30, 30, 30, 30, 30]
        hysteresis = [50.5, 10.5, 7.5, 5.5, 3.5, 1.5, 1, 0.9, 0.15]
        relay_num = config_dict["mks"]["relays"]["vacuum_pump"]["relay_num"]

        self.mks.set_relay_mode(relay_num, "SET")
        self.mks_teensy.activate_relay(config_dict["mks"]["teensy relays"].index("valve_vacuum"))
        self.mks_teensy.deactivate_relay(config_dict["mks"]["teensy relays"].index("valve_vent2"))
        for p, w, h in zip(set_pressures, waits, hysteresis):
            t = 0.0
            in_hyst = True
            while t < w and self.degass_running:
                if self.mks.pressures[1] >= h:
                    in_hyst = True
                while (in_hyst and self.mks.pressures[1] >= p and self.degass_running):
                    self.mks_teensy.activate_relay(config_dict["mks"]["teensy relays"].index("valve_pump2"))
                    time.sleep(0.1)
                in_hyst = False
                self.mks_teensy.deactivate_relay(config_dict["mks"]["teensy relays"].index("valve_pump2"))
                time.sleep(0.1)
                t += 0.1
        self.degass_state = "finish"
        socketio.emit(f"update_degass_state", self.degass_state, namespace="/printing")


    def finish_degass(self):
        relay_num = config_dict["mks"]["relays"]["vacuum_pump"]["relay_num"]
        self.mks_teensy.activate_relay(config_dict["mks"]["teensy relays"].index("valve_vent2"))
        self.mks_teensy.deactivate_relay(config_dict["mks"]["teensy relays"].index("valve_vacuum"))
        self.mks.set_relay_mode(relay_num, "CLEAR")
        for _ in range(100):
            if self.mks.pressures[1] >= config_dict["mks"]["atm pressure"]:
                break
            time.sleep(0.1)
        self.mks_teensy.deactivate_relay(config_dict["mks"]["teensy relays"].index("valve_vent2"))