import time
import logging
from datetime import datetime

from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.hardware_configuration.hardware_configuration import driver_handles
from printer_server.printer_control.print_control import PrintControl, PrintingException, run_in_thread

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class BPControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.bp_stage = driver_handles.bp_stage
        self.external_control = driver_handles.external_control

        # log files
        self.position_log = str(self.current_job / "logs" / "position_data.csv")

    def create_logs(self):
        super().create_logs()

        async_file_hander.write(
            self.position_log,
            "layer,duplicate,start_time,end_time,",
        )
        async_file_hander.write(
            self.position_log,
            "start_position,end_position,thickness_um,squeeze\n",
        )
        self.bp_stage.setup_log_file(str(self.current_job / "logs"))

    def connect_hardware(self):
        self.bp_thread = Thread(log, name="bp_control_connect_thread", target=self.bp_stage.connect)
        self.bp_thread.start()
        super().connect_hardware()
        self.bp_thread.join()
        if not self.bp_stage.connected or self.bp_thread.exception is not None:
            log.error("Build platform stage failed to connect!")
            self.failed_hardware["Build Platform Stage"] = self.bp_stage

    def initialize_hardware(self):
        bp_pos = self.bp_stage.top_position
        self.bp_thread = Thread(log, name="bp_control_init_thread", target=self.bp_stage.initialize_and_positionBP, args=[bp_pos, self.external_control.get_enable()])
        self.bp_thread.start()
        super().initialize_hardware()
        self.bp_thread.join()
        if self.bp_thread.exception is not None:
            log.error("Build platform stage failed to initialize!")
            self.failed_hardware["Build Platform Stage"] = self.bp_stage

    def move_build_platform_up(self, position_settings):
        """Moves the build platform up according to the position_settings"""
        try:
            initial_wait = position_settings["Initial wait (ms)"] / 1000
            up_distance = position_settings["Distance up (mm)"]
            up_speed = position_settings["BP up speed (mm/sec)"]
            up_acceleration = position_settings["BP up acceleration (mm/sec^2)"]

            time.sleep(initial_wait)
            self.write_to_event_log("Start Up Movement")
            self.bp_stage.absMoveBP(
                mm=self.print_position - up_distance,
                speed=up_speed,
                acceleration=up_acceleration,
                wait_for_settling=False
            )
            self.write_to_event_log("Finish Up Movement")
        except Exception as ex:
            log.critical("Unable to move build platform stage (%s)", ex, exc_info=True)
            self.failed_hardware["Build Platform Stage"] = self.bp_stage
            raise PrintingException()

    def move_build_platform_down(self, position_settings):
        """Moves the build platform down according to the position_settings"""
        try:
            up_wait = position_settings["Up wait (ms)"] / 1000
            down_speed = position_settings["BP down speed (mm/sec)"]
            down_acceleration = position_settings["BP down acceleration (mm/sec^2)"]

            time.sleep(up_wait)
            self.write_to_event_log("Start Down Movement")
            self.bp_stage.absMoveBP(
                mm=self.print_position,
                speed=down_speed,
                acceleration=down_acceleration,
            )
            self.write_to_event_log("Finish Down Movement")
        except Exception as ex:
            log.critical("Unable to move build platform stage (%s)", ex, exc_info=True)
            self.failed_hardware["Build Platform Stage"] = self.bp_stage
            raise PrintingException()

    def move_build_platform(self, position_settings, layer):
        """Perform the build platform movements for a layer according to
        the position_settings.
        """
        try:
            final_wait = position_settings["Final wait (ms)"] / 1000
            layer_thickness = position_settings["Layer thickness (um)"] / 1000

            start_position = self.bp_stage.getBPPosition()
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            self.move_build_platform_up(position_settings)
            self.print_position -= layer_thickness
            self.move_build_platform_down(position_settings)

            force_squeeze = position_settings.get("Enable force squeeze", False)
            if force_squeeze:
                self.force_squeeze(position_settings, layer)
            time.sleep(final_wait)

            end_position = self.bp_stage.getBPPosition()
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            thickness = (end_position - start_position) * 1000
            async_file_hander.write(
                self.position_log,
                f"{layer[0]},{layer[1]},{start_time},{end_time},",
            )
            async_file_hander.write(
                self.position_log,
                f"{start_position},{end_position},{thickness},{force_squeeze}\n",
            )
        except Exception as ex:
            log.critical("Unable to communicate with build platform stage (%s)", ex, exc_info=True)
            self.failed_hardware["Build Platform Stage"] = self.bp_stage
            raise PrintingException()

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self):
        """Lower the build platform for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            try:
                self.bp_stage.logging_start()
                self.bp_stage.absMoveBP(mm=self.bp_stage.bottom_position)
                # self.bp_stage.absMoveBP(mm=self.bp_stage.bottom_position-12)
                # self.bp_stage.absMoveBP(mm=self.bp_stage.bottom_position, speed=0.5)
            except Exception as ex:
                log.critical("Unable to move build platform stage (%s)", ex, exc_info=True)
                self.failed_hardware["Build Platform Stage"] = self.bp_stage
                raise PrintingException()
            super().planarization_step_1()

    @run_in_thread("planarized", "Planarization Step 2")
    def planarization_step_2(self):
        try:
            self.planarized_position = self.bp_stage.getBPPosition()
        except Exception as ex:
            log.critical("Unable to communicate with build platform stage (%s)", ex, exc_info=True)
            self.failed_hardware["Build Platform Stage"] = self.bp_stage
            raise PrintingException()
        super().planarization_step_2()

    
    def resume(self):
        """Resume a paused print."""
        if self.state != "paused":
            return
        try:
            layer = self.layer_map[self.next_layer-1]
            current_layer_settings = self.print_settings["Layers"][layer[0]]
            position_settings = self.get_position_settings(current_layer_settings)
            layer_thickness = position_settings["Layer thickness (um)"] / 1000
            down_speed = position_settings["BP down speed (mm/sec)"]
            down_acceleration = position_settings["BP down acceleration (mm/sec^2)"]

            self.print_position = self.paused_position
            self.paused_position = None

            self.bp_stage.absMoveBP(mm=self.print_position-layer_thickness)
            self.bp_stage.absMoveBP(
                mm=self.print_position,
                speed=down_speed,
                acceleration=down_acceleration,
            )
        except Exception as ex:
            log.critical("Unable to move build platform stage (%s)", ex, exc_info=True)
            self.failed_hardware["Build Platform Stage"] = self.bp_stage
            raise PrintingException()
        super().resume()

    def pre_print_tasks(self):
        # move build platform to the starting position if this is the first layer
        if self.next_layer == 0:
            try:
                self.bp_stage.absMoveBP(mm=self.planarized_position)
            except Exception as ex:
                log.critical("Unable to move build platform stage (%s)", ex, exc_info=True)
                self.failed_hardware["Build Platform Stage"] = self.bp_stage
                raise PrintingException()
        super().pre_print_tasks()

    def post_print_tasks(self):
        # set paused position
        if self.printing_paused.is_set():
            try:
                self.paused_position = self.bp_stage.getBPPosition()
            except Exception as ex:
                log.critical("Unable to communicate with build platform stage (%s)", ex, exc_info=True)
                self.failed_hardware["Build Platform Stage"] = self.bp_stage
                raise PrintingException()
            
        super().post_print_tasks()
        try:
            defaults_layer_settings = self.print_settings.get("Default layer settings")
            default_position_settings = defaults_layer_settings.get("Position settings")
            self.move_build_platform_up(default_position_settings)
        except:
            # needed for json 999
            pass

        bp_pos = self.bp_stage.top_position
        self.bp_thread = self.bp_stage.threadedBPMove(log, bp_pos, join=False, speed=None, acceleration=None)
              
    def post_print_joins(self):
        if self.bp_thread is not None:
            self.bp_thread.join()
            if self.bp_thread.exception is not None:
                log.critical("Unable to move build platform stage")
                self.failed_hardware["Build Platform Stage"] = self.bp_stage
                raise PrintingException()
        return super().post_print_joins()

    def finish_print(self):
        try:
            self.bp_stage.logging_stop()
            self.bp_stage.setup_log_file(None)
        except Exception as ex:
            log.critical("Unable to communicate with build platform stage (%s)", ex, exc_info=True)
            self.failed_hardware["Build Platform Stage"] = self.bp_stage
            raise PrintingException()
        super().finish_print()