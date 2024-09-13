import time
import logging

import printer_server.views.home as home
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles
from printer_server.printer_control.print_control import PrintControl, run_in_thread
# from printer_server.printer_control.print_control_subclasses import BPControl

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# class LoadcellControl(BPControl):
class LoadcellControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.loadcell = driver_handles.loadcell

        # log files
        self.loadcell_log = str(self.current_job / "logs" / "loadcell_data.csv")
        
        # loadcell graph variables
        self.loadcell_running = False
        self.loadcell_thread = None

    def create_logs(self):
        super().create_logs()

        async_file_hander.write(
            self.loadcell_log, "system_time,loadcell_time,index,raw_data,newtons\n"
        )
        self.loadcell.set_log_file(self.loadcell_log)

    def loadcell_graph_loop(self):
        if not self.loadcell_running:
            self.loadcell_running = True
            while self.loadcell_running:
                data = self.loadcell.get_current_data()
                home.update_loadcell_graph({"data": data})
                time.sleep(0.05)

    def force_squeeze(self, position_settings, layer):
        squeeze_count = position_settings.get("Squeeze count", 1)
        final_wait = position_settings["Final wait (ms)"] / 1000
        for i in range(squeeze_count):
            self.write_to_event_log("Start Force Squeeze")
            self.squeeze_resin(position_settings, layer)
            self.write_to_event_log("Finish Force Squeeze")
            if i < squeeze_count-1:
                time.sleep(final_wait)

    def squeeze_resin(self, position_settings, layer):
        squeeze_target = position_settings["Squeeze force (N)"]
        squeeze_wait = position_settings["Squeeze wait (ms)"] / 1000

        first_count = self.move_bp_to_force(squeeze_target - 5, speed=0.5)
        second_count = self.move_bp_to_force(squeeze_target - 0.5, speed=0.05)
        third_count = self.move_bp_to_force(squeeze_target, speed=0.005)
        count = first_count + second_count + third_count

        log.info("Squeeze force reached %s steps", count)
        log.info("Squeeze force: %s", self.loadcell.get_current_force())
        log.info("Squeeze position: %s", self.bp_stage.getBPPosition())

        if self.loadcell.get_current_force() > squeeze_target * 1.10:
            log.warning("Move_to_force overshot target value.")

        time.sleep(squeeze_wait)

        self.bp_stage.absMoveBP(mm=self.print_position, speed=50, acceleration=5)

    def move_bp_to_force(
        self, target_force, speed, acceleration=100, error_threshold=None
    ):
        """Move the build platform until the target force is achieved.

        force - Target force.
        speed - Speed in mm/sec. Negative speed means move up.
        """
        force = self.loadcell.get_current_force()
        forces = []
        count = 0
        if (speed < 0 and force > target_force) or (speed > 0 and force < target_force):
            self.bp_stage.startBPJog(speed=speed, acceleration=acceleration)
            while (speed < 0 and force > target_force) or (
                speed > 0 and force < target_force
            ):
                time.sleep(0.01)
                force = self.loadcell.get_current_force()
                log.debug("Loadcell force: %s", force)
                count += 1
                forces.append(force)
                if len(forces) <= 33:
                    continue
                forces.pop(0)

                if error_threshold is not None:
                    # print(f"{abs(forces[0] - forces[-1])}, {error_threshold}")
                    if abs(forces[0] - forces[-1]) < error_threshold:
                        self.bp_stage.stopBPJog()
                        time.sleep(0.02)
                        return None
            self.bp_stage.stopBPJog()
            time.sleep(0.02)
        return count

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self):
        """Lower the build platform for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            self.loadcell.start()   
            time.sleep(0.5)
            if self.loadcell_thread is None:
                home.clear_loadcell_graph()
                self.loadcell_thread = Thread(log, name="print_control_loadcell_graph_thread", target=self.loadcell_graph_loop)
                self.loadcell_thread.start()
            loadcell_start_force = self.loadcell.get_current_force()
            super().planarization_step_1()
            if config_dict["loadcell"]["loadcell_planarization_enabled"]:
                log.debug("Loadcell force (pre-step 1): %s", loadcell_start_force)
                target_force = config_dict["loadcell"]["loadcell_planarization_force"]
                if (
                    self.move_bp_to_force(target_force, speed=2.5, error_threshold=0.25)
                    is None
                ):
                    log.error("Did not reach target planarization force.")
                    return
                time.sleep(0.5)
                log.info(
                    "Loadcell force (post-step 1): %s", self.loadcell.get_current_force()
                )
                log.info("Loadcell position (post-step 1): %s", self.bp_stage.getBPPosition())
            else:
                # estimate a 2mm movement for planarization
                self.bp_stage.relMoveBP(mm=2.0, speed=2.5)

    @run_in_thread("planarized", "Planarization Step 2")
    def planarization_step_2(self):
        super().planarization_step_2()
        """Raise the build platform to begin printing."""
        if config_dict["loadcell"]["loadcell_planarization_enabled"]:
            if self.state == "planarizing":
                self.planarization_step_3()

    def planarization_step_3(self):
        """Raise the build platform to its starting postion.

        This is accomplished by first moving up quickly until the
        measured force is within 5 newtons of the target force, then
        moving up more slowly until the measured force reaches the
        target force.
        """
        target_force = config_dict["loadcell"]["loadcell_print_start_force"]
        first_count = self.move_bp_to_force(
            target_force + 5, speed=-0.5, error_threshold=2.5
        )
        if first_count is None:
            log.error("Loadcell planarization failed. Check build platform screw.")
            return
        second_count = self.move_bp_to_force(target_force + 0.5, speed=-0.05)
        third_count = self.move_bp_to_force(target_force, speed=-0.005)
        count = first_count + second_count + third_count

        self.planarized_position = self.bp_stage.getBPPosition()
        self.print_position = self.planarized_position
        log.info("Loadcell planarized %s steps", count)
        log.info("Loadcell force (post-step 2): %s", self.loadcell.get_current_force())
        log.info("Loadcell position (post-step 2): %s", self.planarized_position)
        if self.loadcell.get_current_force() < target_force * 0.90:
            log.warning("Move_to_force overshot target value")

    def connect_hardware(self):
        loadcell_t = Thread(log, name="loadcell_control_setup_thread", target=self.loadcell.connect, args=[self.shutdown])
        loadcell_t.start()
        super().connect_hardware()
        loadcell_t.join()
        if not self.loadcell.connected:
            log.error("Loadcell failed to connect!")
            self.failed_hardware["Loadcell"] = self.loadcell
            self.all_hardware_connected = False

    def initialize_hardware(self):
        loadcell_t = Thread(log, name="loadcell_control_init_thread", target=self.loadcell.initialize, args=[])
        loadcell_t.start()
        super().initialize_hardware()
        loadcell_t.join()

    def print_worker(self):
        if self.state != "printing":
            return
        if not self.loadcell.running:
            self.loadcell.start()
        super().print_worker()
        if self.printing_paused.is_set():
            self.loadcell.pause()

    def finish_print(self):
        self.loadcell.stop()
        self.loadcell_running = False
        self.loadcell_thread = None
        home.clear_loadcell_graph()
        self.loadcell.set_log_file(None)
        super().finish_print()