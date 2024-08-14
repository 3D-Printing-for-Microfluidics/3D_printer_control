import time
import logging

from printer_server.extensions import socketio
from printer_server.threading_wrapper import Thread
from printer_server.printer_control.print_control import PrintControl
from printer_server.hardware_configuration.hardware_configuration import driver_handles, config_dict

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class VacuumControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.mks = driver_handles.mks
        self.mks_teensy = driver_handles.mks_teensy
        self.degas_running = False
        self.degas_thread = None
        self.degas_state = None

    def connect_hardware(self):
        mks_thread = Thread(log, name="mks_connect_thread", target=self.mks.connect, args=[self.shutdown])
        mks_teensy_thread = Thread(log, name="mks_teensy_thread", target=self.mks_teensy.connect, args=[self.shutdown])
        mks_thread.start()
        mks_teensy_thread.start()
        super().connect_hardware()
        mks_thread.join()
        mks_teensy_thread.join()
        if not self.mks.connected:
            log.error("MKS failed to connect!")
            self.all_hardware_connected = False
        if not self.mks_teensy.connected:
            log.error("MKS Teensy failed to connect!")
            self.all_hardware_connected = False

    def initialize_hardware(self):
        mks_thread = Thread(log, name="mks_init_thread", target=self.mks.initialize, args=[])
        mks_thread.start()
        super().initialize_hardware()
        mks_thread.join()
        self.degas_state = "idle"
        socketio.emit(f"update_degas_state", self.degas_state, namespace="/printing")

    def degas(self, msg):
        if msg == "run":
            self.degas_running = True
            self.degas_thread = Thread(log, name="degas_thread", target=self.run_degas, args=[])
            self.degas_thread.start()
            self.degas_state = "running"
        elif msg == "stop":
            self.degas_running = False
            self.degas_thread.join()
            self.finish_degas()
            self.degas_state = "idle"
        elif msg == "finish":
            self.finish_degas()
            self.degas_state = "idle"
        socketio.emit(f"update_degas_state", self.degas_state, namespace="/printing")

    def run_degas(self):
        set_pressures = [50, 10, 7, 5, 3, 1, 0.9, 0.8, 0.1]
        waits = [30, 30, 30, 30, 30, 30, 30, 30, 30]
        hysteresis = [50.5, 10.5, 7.5, 5.5, 3.5, 1.5, 1, 0.9, 0.15]
        relay_num = config_dict["mks"]["relays"]["vacuum_pump"]["relay_num"]

        self.mks.set_relay_mode(relay_num, "SET")
        self.mks_teensy.switch_relay(config_dict["mks"]["teensy relays"].index("valve_vacuum"), True)
        self.mks_teensy.switch_relay(config_dict["mks"]["teensy relays"].index("valve_vent2"), False, force=True)
        pumping = False
        for p, w, h in zip(set_pressures, waits, hysteresis):
            log.info("Degassing to %s Torr and holding for %s seconds", p, w)
            t = 0.0
            while t < w and self.degas_running:
                if self.mks.pressures[1] >= h:
                    pumping = True
                    self.mks_teensy.switch_relay(config_dict["mks"]["teensy relays"].index("valve_pump2"), True, force=True)
                while (pumping and self.mks.pressures[1] >= p and self.degas_running):
                    time.sleep(0.1)
                if pumping:
                    pumping = False
                    self.mks_teensy.switch_relay(config_dict["mks"]["teensy relays"].index("valve_pump2"), False, force=True)
                time.sleep(0.1)
                t += 0.1
        self.degas_state = "finish"
        socketio.emit(f"update_degas_state", self.degas_state, namespace="/printing")


    def finish_degas(self):
        relay_num = config_dict["mks"]["relays"]["vacuum_pump"]["relay_num"]
        self.mks_teensy.switch_relay(config_dict["mks"]["teensy relays"].index("valve_pump2"), False, force=True)
        self.mks_teensy.switch_relay(config_dict["mks"]["teensy relays"].index("valve_vent2"), True, force=True)
        self.mks_teensy.switch_relay(config_dict["mks"]["teensy relays"].index("valve_vacuum"), False)
        self.mks.set_relay_mode(relay_num, "CLEAR")
        for _ in range(100):
            if self.mks.pressures[1] >= config_dict["mks"]["atm pressure"]:
                break
            time.sleep(0.1)
        self.mks_teensy.switch_relay(config_dict["mks"]["teensy relays"].index("valve_vent2"), False, force=True)