from printer_server.printer_control.print_control import *

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class XYControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.xy_stage = driver_handles.xy_stage
        self.coord_systems = config_dict["coord_systems"]

    def create_logs(self):
        super().create_logs()
        self.xy_stage.setup_log_file(str(self.current_job))

    def connect_hardware(self):
        xy_thread = Thread(log, name="xy_control_setup_thread", target=self.xy_stage.connect, args=[self.shutdown])
        xy_thread.start()
        super().connect_hardware()
        xy_thread.join()
        if not self.xy_stage.connected:
            self.all_hardware_connected = False

    def initalize_hardware(self):
        x_pos = self.coord_systems["visitech"]["X"]
        y_pos = self.coord_systems["visitech"]["Y"]
        xy_threads = self.xy_stage.initialize_and_positionXY(x_pos, y_pos)
        super().initalize_hardware()
        for thread in xy_threads:
            if thread is not None:
                thread.join()
        self.xy_stage.initialized = True

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self):
        """Lower the build platform for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            super().planarization_step_1()
            self.xy_stage.logging_start()

    def post_print_tasks(self):
        # set paused position
        x_pos = self.coord_systems["visitech"]["X"]
        y_pos = self.coord_systems["visitech"]["Y"]
        xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False, speed_x=None, speed_y=None, acceleration_x=None, acceleration_y=None)
        for thread in xy_threads:
            if thread is not None:
                thread.join()

    def finish_print(self):
        self.xy_stage.logging_stop()
        self.xy_stage.setup_log_file(None)
        super().finish_print()