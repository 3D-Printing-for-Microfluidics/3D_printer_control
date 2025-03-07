import time
import logging

from printer_server.extensions import socketio
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.printer_control.print_control import PrintControl, PrintingException, run_in_thread
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

        # log files
        self.pressure_planarization_log = str(self.current_job / "logs" / "pressure_data.csv")
        self.pressure_log = str(self.current_job / "logs" / "pressure_data.csv")

    def create_logs(self):
        super().create_logs()
        self.mks.setup_log_file(str(self.current_job / "logs"))

    def connect_hardware(self):
        mks_thread = Thread(log, name="mks_connect_thread", target=self.mks.connect)
        mks_teensy_thread = Thread(log, name="mks_teensy_connect_thread", target=self.mks_teensy.connect)
        mks_thread.start()
        mks_teensy_thread.start()
        super().connect_hardware()
        mks_thread.join()
        mks_teensy_thread.join()
        if not self.mks.connected or mks_thread.exception is not None:
            log.error("MKS failed to connect!")
            self.failed_hardware["MKS Controller"] = self.mks
        if not self.mks_teensy.connected or mks_teensy_thread.exception is not None:
            log.error("MKS Teensy failed to connect!")
            self.failed_hardware["MKS Teensy"] = self.mks_teensy

    def initialize_hardware(self):
        mks_thread = Thread(log, name="mks_init_thread", target=self.mks.initialize, args=[])
        mks_thread.start()
        super().initialize_hardware()
        mks_thread.join()
        if mks_thread.exception is not None:
            log.error("MKS failed to initialize!")
            self.failed_hardware["MKS Controller"] = self.mks
            return
        self.degas_state = "idle"
        socketio.emit(f"update_degas_state", self.degas_state, namespace="/printing")

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self):
        """Lower the build platform for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            try:
                self.mks.logging_start()
            except Exception as ex:
                log.warning("Unable to communicate with mks controller (%s)", ex, exc_info=True)
            super().planarization_step_1()

    @run_in_thread("planarized", "Planarization Step 2")
    def planarization_step_2(self):
        # lower bell jar and start vacuum system
        try:
            log.info("Lowering bell jar and starting vacuum system")
            self.mks_teensy.move_crane_bottom()  
            relay_num = config_dict["mks"]["relays"]["vacuum_pump"]["relay_num"]
            self.mks.set_relay_mode(relay_num, "SET")
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_vacuum"), True)
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_pump1"), True)
        except Exception as ex:
            log.critical("Unable to control vacuum system or bell jar (%s)", ex, exc_info=True)
            self.failed_hardware["MKS Teensy"] = self.mks_teensy
            raise PrintingException()
        super().planarization_step_2()

    def pre_print_tasks(self):
        # wait until vacuum system is ready
        log.info("Waiting for vacuum system to reach target pressure")
        if self.next_layer == 0:
            try:
                bell_jar_target = config_dict["mks"]["target"][0]
                bell_jar_reading = self.mks.pressures[0]
                while bell_jar_reading > bell_jar_target:
                    bell_jar_reading = self.mks.pressures[0]
                    time.sleep(0.1)
            except Exception as ex:
                log.critical("Railed to read vacuum levels (%s)", ex, exc_info=True)
                self.failed_hardware["Vacuum Controller"] = self.mks
                raise PrintingException()
        super().pre_print_tasks()

    def finish_print(self):
        # vent vaccum system and raise bell jar
        try:
            log.info("Venting vacuum system")
            relay_num = config_dict["mks"]["relays"]["vacuum_pump"]["relay_num"]
            self.mks.set_relay_mode(relay_num, "CLEAR")
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_vacuum"), False)
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_pump1"), False)
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_vent1"), True)

            bell_jar_target = config_dict["mks"]["relays"]["crane"]["setpoint"]
            bell_jar_reading = self.mks.pressures[0]
            crane_enable = False
            
            
            while not crane_enable and bell_jar_reading < bell_jar_target:
                bell_jar_reading = self.mks.pressures[0]
                relay_settings_list = self.mks.get_all_relay_status()
                for k, v in config_dict["mks"]["relays"].items():
                    if k == "crane":
                        crane_enable = relay_settings_list[v["relay_num"]-1]
                log.info(bell_jar_reading, relay_settings_list, crane_enable)
                time.sleep(0.1)
            
            time.sleep(15)

            log.info("Venting finished, raising bell jar")
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_vent1"), False)
            # self.mks_teensy.move_crane_top()
            
        except Exception as ex:
            log.critical("Unable to control vacuum system or bell jar (%s)", ex, exc_info=True)
        super().finish_print()
        try:
            self.mks.logging_stop()
            self.mks.setup_log_file(None)
        except Exception as ex:
            log.critical("Unable to communicate with mks controller (%s)", ex, exc_info=True)

    def degas(self, msg):
        if msg == "run":
            self.degas_running = True
            self.degas_thread = Thread(log, name="degas_thread", target=self.run_degas, args=[])
            self.degas_thread.start()
            self.degas_state = "running"
        elif msg == "stop":
            self.degas_running = False
            self.degas_thread.join()
            if self.degas_thread.exception is not None:
                log.warning("Error occured in degassing thread")
            self.finish_degas()
            self.degas_state = "idle"
        elif msg == "finish":
            self.degas_state = "idle"
            self.finish_degas()
        socketio.emit(f"update_degas_state", self.degas_state, namespace="/printing")

    def run_degas(self):
        try:
            set_pressures = [50, 10, 7, 5, 3, 1, 0.9, 0.8, 0.1]
            waits = [30, 30, 30, 30, 30, 30, 30, 30, 30]
            hysteresis = [50.5, 10.5, 7.5, 5.5, 3.5, 1.5, 1, 0.9, 0.15]
            relay_num = config_dict["mks"]["relays"]["vacuum_pump"]["relay_num"]

            self.mks.set_relay_mode(relay_num, "SET")
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_vacuum"), True)
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("stirring"), True)
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_vent2"), False, force=True)
            pumping = False
            for p, w, h in zip(set_pressures, waits, hysteresis):
                log.info("Degassing to %s Torr and holding for %s seconds", p, w)
                t = 0.0
                while t < w and self.degas_running:
                    if self.mks.pressures[1] >= h:
                        pumping = True
                        self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_pump2"), True)
                    while (pumping and self.mks.pressures[1] >= p and self.degas_running):
                        time.sleep(0.1)
                    if pumping:
                        pumping = False
                        self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_pump2"), False)
                    time.sleep(0.1)
                    t += 0.1
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_pump2"), True)
            self.degas_state = "finish"
            socketio.emit(f"update_degas_state", self.degas_state, namespace="/printing")

            stirring = True
            counter = 0
            while self.degas_state == "finish":
                if counter == 150 and stirring:
                    counter = 0
                    stirring = False
                    self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("stirring"), stirring)
                if counter == 150 and not stirring: 
                    counter = 0
                    stirring = True
                    self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("stirring"), stirring)
                counter += 1
                time.sleep(0.1)
        except Exception as ex:
            log.warning("Error occured in degassing thread (%s)", ex, exc_info=True)


    def finish_degas(self):
        try:
            relay_num = config_dict["mks"]["relays"]["vacuum_pump"]["relay_num"]
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("stirring"), False)
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_pump2"), False)
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_vent2"), True)
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_vacuum"), False)
            self.mks.set_relay_mode(relay_num, "CLEAR")
            for _ in range(200):
                if self.mks.pressures[1] >= config_dict["mks"]["atm pressure"]:
                    break
                time.sleep(0.1)
            self.mks_teensy.switch_relay(config_dict["mks_teensy"]["relays"].index("valve_vent2"), False)
        except Exception as ex:
            log.warning("Error occured in degassing thread (%s)", ex, exc_info=True)