import os
import time
import json
import shutil
import logging
import threading
from pathlib import Path
from flask import request
from functools import wraps
from datetime import datetime
from zipfile import ZipFile, BadZipFile

import printer_server.views.home as home
from printer_server.extensions import db
from printer_server.settings import Config
from printer_server.models import PrintQueue, PrintRecord
from printer_server.print_file_validator import validate_schema, read_json, expand_json
from printer_server.hardware_configuration import config_dict
from printer_server.async_file_handler import async_file_hander
from printer_server.hardware_configuration import driver_handles
from printer_server.views.manual_controls import (
    get_last_calibration_positions_from_logs,
)

# from printer_server.drivers.kdc101.kdc101_snip import get_kdc_positions
# from printer_server.drivers.tiptilt.tiptilt_snip import get_tiptilt_positions

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def move_all_galil(
    galil,
    x,
    y,
    z,
    bp,
    join=True,
    speed_x=None,
    speed_y=None,
    speed_z=None,
    speed_bp=None,
    acceleration_x=None,
    acceleration_y=None,
    acceleration_z=None,
    acceleration_bp=None
):
    """
    Starts multithreaded movement on all of the galil axes. If any axis is set to none, it will not move.
    If join is set to true, the movements will join before returning
    """
    threads = [None, None, None, None]
    if x is not None:
        threads[0] = threading.Thread(
            target=galil.absMove,
            kwargs={
                "mm": x / 1000,
                "speed": speed_x,
                "acceleration": acceleration_x,
                "axis": "X",
            },
        )
        threads[0].start()
    if y is not None:
        threads[1] = threading.Thread(
            target=galil.absMove,
            kwargs={
                "mm": y / 1000,
                "speed": speed_y,
                "acceleration": acceleration_y,
                "axis": "Y",
            },
        )
        threads[1].start()
    if z is not None:
        threads[2] = threading.Thread(
            target=galil.absMove,
            kwargs={
                "mm": z / 1000,
                "speed": speed_z,
                "acceleration": acceleration_z,
                "axis": "Focus",
            },
        )
        threads[2].start()

    if bp is not None:
        threads[3] = threading.Thread(
            target=galil.absMove,
            kwargs={
                "mm": bp / 1000,
                "speed": speed_bp,
                "acceleration": acceleration_bp,
                "axis": "Build Platform",
            },
        )
        threads[3].start()

    if join:
        for thread in threads:
            if thread is not None:
                thread.join()
    else:
        return threads


def get_last_focused_position_from_logs():
    """Return the last focused position for the distance axis from the
    position log file.
    """
    return get_last_calibration_positions_from_logs()["distance"]


def has_bad_metadata(filename):
    """Check to see if the zip file has a hidden __MACOSX folder."""
    try:
        with ZipFile(filename, "r") as input_file:
            for item in input_file.namelist():
                if item.startswith("__MACOSX/"):
                    return True
        return False
    except BadZipFile:
        return False


def clean_uploaded_file(filename):
    """Remove unwanted hidden files created by MAC OS in zipfiles."""
    temp_filename = Path(Config.UPLOAD_FOLDER) / "queue" / "temp.zip"
    with ZipFile(filename, "r") as old_file, ZipFile(temp_filename, "w") as new_file:
        for item in old_file.infolist():
            buffer = old_file.read(item.filename)
            if not str(item.filename).startswith("__MACOSX/"):
                new_file.writestr(item, buffer)
    shutil.move(temp_filename, filename)


def run_in_thread(state, text):
    """Wrap long running printer operation methods. The wrapped methods
    push the 3D printer state changes to clients and finish their
    operations in another thread.

    :param str state: 3D printer state
    :param str text: printer message for the message box in webpage
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(self, *args, **kwargs):
            if kwargs.get("run_in_thread", True):

                def func(self, *args, **kwargs):
                    f(self, *args, **kwargs)
                    self.state = state
                    home.update_printer_state(self.state, dict())

                msg = {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "text": text,
                }
                log.info(msg["text"])
                home.update_printer_state("busy", msg)
                _thread = threading.Thread(
                    target=func, args=(self, *args), kwargs={**kwargs}
                )
                _thread.start()
            else:
                f(self, *args, **kwargs)

        return decorated_function

    return decorator


class PrintControl:
    """
    The PrintControl class contains all the 3D printer
    operations. It wraps the ``threading.Thread`` object such that
    a new thread is instantiated every time the 3D printer starts
    a long operation.
    """

    def __init__(self):
        self._state = "uninitialized"

        # hardware handles
        self.galil = driver_handles.galil
        self.tiptilt = driver_handles.tiptilt
        self.loadcell = driver_handles.loadcell

        # loadcell graph variables
        self.loadcell_running = False
        self.loadcell_thread = None

        # folders relevant to printing
        self.queue = Path(Config.UPLOAD_FOLDER) / Path("queue")
        self.current_job = Path(Config.UPLOAD_FOLDER) / Path("current_job")
        self.print_history = Path(Config.UPLOAD_FOLDER) / Path("print_history")

        # log files
        self.position_log = str(self.current_job / "position_data.csv")
        self.exposure_log = str(self.current_job / "exposure_data.log")
        self.loadcell_log = str(self.current_job / "loadcell_data.csv")
        self.movement_log = str(self.current_job / "movement_data.csv")
        self.event_log = str(self.current_job / "event_log.csv")

        # threads
        self.galil_thread = None

        # values used during printing
        self.image = None
        self.planarized_position = None
        self.focused_position = None
        self.print_position = None
        self.print_settings = None
        self.exposure_time_ms = None
        self.power = None
        self.layer_map = []
        self.next_layer = 0
        self.exposure_count = 0
        self.exposure_index = 0
        self.paused_position = None
        self.print_thread = None  # will be initialized later on start
        self.printing_stopped = threading.Event()
        self.printing_paused = threading.Event()

    @property
    def state(self):
        """Return the current state."""
        return self._state

    @state.setter
    def state(self, state):
        """Set the current state."""
        if state in [
            "uninitialized",
            "initialized",
            "planarizing",
            "planarized",
            "printing",
            "paused",
            "stopped",
            "completed",
            "busy",
        ]:
            self._state = state
        else:
            raise ValueError(f"Invalid state: {state}")

    def loadcell_graph_loop(self):
        if not self.loadcell_running:
            self.loadcell_running = True
            while self.loadcell_running:
                data = self.loadcell.get_current_data()
                home.update_loadcell_graph({"data": data})
                time.sleep(0.05)

    def load_print_job(self, job_id):
        """
        The selected print job is retrieved from the Print Queue table
        in the database. The current_job folder is cleared and the job
        is extracted there. The original (still zipped) print file is
        also copied to the print_history folder. A new entry in the
        Print History table in the database is created for the current
        job, and it's entry in the Print Queue table is deleted.
        """
        job = PrintQueue.query.get(job_id)
        if not job:
            log.warning("The print job with ID '%s' could not be found.", job_id)
            return False
        zipped_job_file = self.queue / Path(job.zip_filename)

        # clear any old contents from the current_job folder
        try:
            shutil.rmtree(self.current_job)
        except FileNotFoundError:
            pass

        # extract zip from self.queue to self.current_job
        try:
            with ZipFile(zipped_job_file, "r") as f:
                namelist = f.namelist()
                for name in list(namelist):
                    if (".csv" in name) or (".log" in name) or ("exposure_data" in name):
                        namelist.remove(name)
                f.extractall(self.current_job, members=namelist)
        except FileNotFoundError:
            self.delete_job({"job": job_id})
            return False
        return True

    def move_job_to_print_history(self, job_id):
        job = PrintQueue.query.get(job_id)
        if not job:
            log.warning("The print job with ID '%s' could not be found.", job_id)
            return False
        zipped_job_file = self.queue / Path(job.zip_filename)

        # move zip file from self.queue to self.print_history
        os.rename(zipped_job_file, self.print_history / Path(job.zip_filename))

        # save job to Print History table in database
        print_history_entry = PrintRecord(
            original_filename=job.original_filename,
            upload_time=job.upload_time,
            upload_ip=job.upload_ip,
            start_time=datetime.now(),
            start_ip=request.remote_addr,
        )
        print_history_entry.save(commit=False)

        # tell frontend to remove the job from the table and delete it from the database
        self.delete_job({"job": job_id}, delete_on_disk=False)

    def create_logs(self):
        # create logs and overwrite any pre-existing data
        async_file_hander.set_enabled(True)
        async_file_hander.write(
            self.position_log,
            "layer,duplicate,start_time,end_time,loadcell_start_index,",
        )
        async_file_hander.write(
            self.position_log,
            "loadcell_end_index,start_position,end_position,thickness_um,squeeze\n",
        )
        async_file_hander.write(self.exposure_log, "")
        async_file_hander.write(self.event_log, "timestamp,event\n")
        async_file_hander.write(self.movement_log, "timestamp,")
        for a in self.galil.axes_common_names:
            async_file_hander.write(self.movement_log, f"{a} position_mm,")
            async_file_hander.write(self.movement_log, f"{a} status,")
        async_file_hander.write(self.movement_log, "\n")
        async_file_hander.write(
            self.loadcell_log, "system_time,loadcell_time,index,raw_data,newtons\n"
        )
        async_file_hander.start()
        self.galil.set_log_file(self.movement_log)
        self.loadcell.set_log_file(self.loadcell_log)

    def get_position_settings(self, layer):
        """Return the position settings for the layer."""
        d = self.print_settings.get("Default layer settings").get("Position settings")
        overrides = layer.get("Position settings")
        layer_settings = d.copy()
        if overrides is not None:
            layer_settings.update(overrides)
        return layer_settings

    def get_image_settings(self, layer):
        """Return a list of the image settings for the layer."""
        defaults = self.print_settings.get("Default layer settings").get("Image settings")
        layer_specific_settings = layer.get("Image settings list")

        final_settings = []
        if layer_specific_settings is not None:
            for settings in layer_specific_settings:
                merged = defaults.copy()
                merged.update(settings)
                final_settings.append(merged)
        if not final_settings:
            final_settings.append(defaults.copy())
        return final_settings

    def generate_layer_map(self):
        """Return an array of tuples that represent layers and their
        duplications.
        """
        default_dups = self.print_settings["Default layer settings"][
            "Number of duplications"
        ]
        layers = []
        for i, layer in enumerate(self.print_settings["Layers"]):
            dups = layer.get("Number of duplications", default_dups)
            for j in range(dups):
                layers.append((i, j))
        return layers

    def exposures_in_layer(self, layer):
        """Return the total number of exposures in layer"""
        current_layer_settings = self.print_settings["Layers"][layer[0]]
        image_settings_list = self.get_image_settings(current_layer_settings)
        return len(image_settings_list)

    def total_number_of_exposures(self):
        """Return the total number of exposures including duplicates"""
        count = 0
        for i, layer in enumerate(self.layer_map):
            count += self.exposures_in_layer(layer)
        return count

    def write_to_event_log(self, msg):
        async_file_hander.write(
            self.event_log, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')},{msg}\n"
        )

    def move_build_platform_up(self, position_settings):
        """Moves the build platform up according to the position_settings"""
        inital_wait = position_settings["Initial wait (ms)"] / 1000
        up_distance = position_settings["Distance up (mm)"]
        up_speed = position_settings["BP up speed (mm/sec)"]
        up_acceleration = position_settings["BP up acceleration (mm/sec^2)"]

        time.sleep(inital_wait)
        self.write_to_event_log("Start Up Movement")
        self.galil.absMove(
            mm=self.print_position - up_distance,
            speed=up_speed,
            acceleration=up_acceleration,
            wait_for_settling=False,
        )
        self.write_to_event_log("Finish Up Movement")

    def move_build_platform_down(self, position_settings):
        """Moves the build platform down according to the position_settings"""
        up_wait = position_settings["Up wait (ms)"] / 1000
        down_speed = position_settings["BP down speed (mm/sec)"]
        down_acceleration = position_settings["BP down acceleration (mm/sec^2)"]

        time.sleep(up_wait)
        self.write_to_event_log("Start Down Movement")
        self.galil.absMove(
            mm=self.print_position,
            speed=down_speed,
            acceleration=down_acceleration,
        )
        self.write_to_event_log("Finish Down Movement")

    def move_build_platform(self, position_settings, layer):
        """Perform the build platform movements for a layer according to
        the position_settings.
        """
        final_wait = position_settings["Final wait (ms)"] / 1000
        layer_thickness = position_settings["Layer thickness (um)"] / 1000

        start_position = self.galil.getPosition()
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        start_index = self.loadcell.get_current_loadcell_index()
        self.move_build_platform_up(position_settings)
        self.print_position -= layer_thickness
        self.move_build_platform_down(position_settings)

        force_squeeze = position_settings.get("Enable force squeeze", False)
        squeeze_count = position_settings.get("Squeeze count", 1)
        if force_squeeze:
            for _ in range(squeeze_count):
                self.write_to_event_log("Start Force Squeeze")
                self.squeeze_resin(position_settings, layer)
                self.write_to_event_log("Finish Force Squeeze")
                time.sleep(final_wait)
        else:
            time.sleep(final_wait)
        end_position = self.galil.getPosition()
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        end_index = self.loadcell.get_current_loadcell_index()
        thickness = self.galil.cntsToMm(abs(end_position - start_position) * 1000)
        async_file_hander.write(
            self.position_log,
            f"{layer[0]},{layer[1]},{start_time},{end_time},{start_index},",
        )
        async_file_hander.write(
            self.position_log,
            f"{end_index},{start_position},{end_position},{thickness},{force_squeeze}\n",
        )

    def squeeze_resin(self, position_settings, layer):
        squeeze_target = position_settings["Squeeze force (N)"]
        squeeze_wait = position_settings["Squeeze wait (ms)"] / 1000

        first_count = self.move_bp_to_force(squeeze_target - 5, speed=0.5)
        second_count = self.move_bp_to_force(squeeze_target - 0.5, speed=0.05)
        third_count = self.move_bp_to_force(squeeze_target, speed=0.005)
        count = first_count + second_count + third_count

        log.info("Squeeze force reached %s steps", count)
        log.info("Squeeze force: %s", self.loadcell.get_current_force())
        log.info("Squeeze position: %s", self.galil.getPosition())

        if self.loadcell.get_current_force() > squeeze_target * 1.10:
            log.warning("Move_to_force overshot target value.")

        time.sleep(squeeze_wait)

        self.galil.absMove(
            mm=self.print_position,
            speed=50,
            acceleration=5,
        )

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
            self.galil.startJog(speed=speed, acceleration=acceleration)
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
                        self.galil.stopJog()
                        time.sleep(0.02)
                        return None
            self.galil.stopJog()
            time.sleep(0.02)
        return count

    def get_focus(self):
        log.warn("Base printer_control class does not have a defined focus stage")
        return 0

    @run_in_thread("initialized", "Initialize")
    def initialize(self, run_in_thread=True):
        """Put all hardware into starting configuration."""
        if self.state == "uninitialized":
            self.state = "busy"
            self.tiptilt.connect()
            self.loadcell.connect()

            self.galil_thread = threading.Thread(target=self.galil_setup_thread, args=[])
            self.galil_thread.start()
            self.galil_thread.join()

            self.galil_thread = threading.Thread(
                target=self.galil_finalize_setup_thread, args=[]
            )
            self.galil_thread.start()
            self.galil_thread.join()

    def galil_setup_thread(self):
        """Initialize and home Galil controller"""
        self.galil.connect()
        self.galil.initialize()
        self.galil.home()

        for a in self.galil.axes:
            self.galil.setSpeed(self.galil.getDefaultSpeed(a), axis=a)
            self.galil.setAcceleration(self.galil.getDefaultAcceleration(a), axis=a)

    def galil_finalize_setup_thread(self):
        self.galil.goToZmax()

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self):
        """Lower the build platform for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            self.state = "busy"
            self.loadcell.start()
            self.galil.logging_start()
            time.sleep(0.5)
            if self.loadcell_thread is None:
                home.clear_loadcell_graph()
                self.loadcell_thread = threading.Thread(target=self.loadcell_graph_loop)
                self.loadcell_thread.start()
            loadcell_start_force = self.loadcell.get_current_force()
            self.galil.goToZmin()
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
            else:
                # estimate a 1mm movement for planarization
                self.galil.relMove(mm=2.0, speed=2.5)

    @run_in_thread("planarized", "Planarization Step 2")
    def planarization_step_2(self):
        self.planarized_position = self.galil.getPosition()
        self.print_position = self.galil.cntsToMm(self.planarized_position)
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

        log.info(
            "Loadcell force post planarization: %s", self.loadcell.get_current_force()
        )
        log.debug("Loadcell position: %s", self.planarized_position)
        self.planarized_position = self.galil.getPosition()
        self.print_position = self.galil.cntsToMm(self.planarized_position)
        log.info("Loadcell planarized %s steps", count)
        log.info("Loadcell force (post-step 2): %s", self.loadcell.get_current_force())
        log.info("Loadcell position (post-step 2): %s", self.planarized_position)
        if self.loadcell.get_current_force() < target_force * 0.90:
            log.warning("Move_to_force overshot target value")

    def start(self, job_id):
        """Do all preparatory work for a print, then start the printing
        process in a separate thread.

        The print settings file is parsed and the settings saved, then the
        hardware operations are kicked off in a new thread.
        """
        if self.state != "planarized" or not job_id:
            return

        # load job and create print_history entry
        if not self.load_print_job(job_id):
            return
        self.move_job_to_print_history(job_id)

        # parse and save print_settings
        self.print_settings = read_json(next(self.current_job.rglob("*.json")))
        expand_json(self.print_settings)

        self.next_layer = 0

        # Start async_file_handler
        self.create_logs()

        position = get_last_calibration_positions_from_logs()
        # position = get_kdc_positions()
        dist = position["distance"]
        self.write_to_event_log(f"Distance: {dist}")
        self.focused_position = float(position["distance"])

        # position = get_tiptilt_positions()
        tip = position["tip"]
        self.write_to_event_log(f"Tip: {tip}")
        tilt = position["tilt"]
        self.write_to_event_log(f"Tilt: {tilt}")

        # update frontend progress bar
        self.state = "printing"
        msg = {
            "percent": 0,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "text": "Start Printing",
        }
        log.info(msg["text"])
        home.update_printer_state(self.state, msg)

        self.print_start_time = datetime.now()

        # start printing process in a new thread
        self.app = db.get_app()
        self.print_thread = threading.Thread(target=self.print_worker)
        self.print_thread.start()

    @run_in_thread("paused", "Pause Printing")
    def pause(self):
        """Pause the printing process.

        It is implemented with a threading.Event object,
        printing_paused. The printing_paused.is_set() flag is only
        checked at the beginning of every layer. If `True`, the printing
        will be paused. If the operations of a layer have started, the
        3D printer will finish that layer first. After being paused, the
        3D printer can resume and continue finishing the print job.
        """
        if self.state == "printing":
            self.printing_paused.set()
            self.print_thread.join()

    def resume(self):
        """Resume a paused print."""
        if self.state != "paused":
            return
        log.info("Resuming print...")
        self.galil.absMove(cnts=self.paused_position)
        self.print_position = self.galil.cntsToMm(self.paused_position)
        self.paused_position = None
        self.loadcell.start()
        # update fontend
        self.state = "printing"
        msg = {
            "percent": int(100 * self.exposure_index / self.exposure_count),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "text": "Resume Printing",
        }
        log.info(msg["text"])
        home.update_printer_state(self.state, msg)
        # resume printing in a new thread
        self.app = db.get_app()
        self.print_thread = threading.Thread(target=self.print_worker)
        self.print_thread.start()

    @run_in_thread("stopped", "Stop Printing")
    def stop(self):
        """Stop the printing process.

        This works almost the same as pause, except the 3D printer
        cannot resume and finish the previous print job.
        """
        if self.state in ["printing", "paused"]:
            self.printing_stopped.set()
            if self.printing_paused.is_set():
                self.finish_print()
            else:
                self.print_thread.join()
            log.info("Print stopped.")

    def pre_print_tasks(self):
        return

    def post_print_tasks(self):
        return

    def print_worker(self):
        """Do a 3D print.

        This method should not be called from the main thread since
        it will block the main thread until it is done and cannot be
        interrupted.
        """
        if self.state != "printing":
            return
        # clear old flags
        self.printing_stopped.clear()
        self.printing_paused.clear()

        # generate layer map
        self.layer_map = self.generate_layer_map()
        self.exposure_index = 0
        self.exposure_count = self.total_number_of_exposures()

        self.pre_print_tasks()

        # move build platform to the starting position if this is the first layer
        if self.next_layer == 0:
            self.galil.absMove(cnts=self.planarized_position)

        # iterate over layers
        for i, layer in enumerate(self.layer_map):
            if i < self.next_layer:
                self.exposure_index += self.exposures_in_layer(layer)
                continue  # skip previous layers if print was paused
            if self.printing_paused.is_set():
                self.loadcell.pause()
                break  # pause, don't do anything else
            if self.printing_stopped.is_set():
                break  # pause, don't do anything else
            self.next_layer = i + 1

            # process layer
            self.layer_worker(i, layer)

        # set paused position
        if self.printing_paused.is_set():
            self.paused_position = self.galil.getPosition()

        self.post_print_tasks()

        # finish print
        if not self.printing_paused.is_set():
            self.finish_print()

    def layer_worker(self, i, layer):
        """Process a single layer of the 3D print.

        This method should only be called from inside print_worker.
        """
        # read settings for this layer
        current_layer_settings = self.print_settings["Layers"][layer[0]]
        position_settings = self.get_position_settings(current_layer_settings)
        image_settings_list = self.get_image_settings(current_layer_settings)

        # update log messages
        msg = f"Layer {layer[0]}-{layer[1]}" if layer[1] else f"Layer {layer[0]}"
        log.info(msg)
        self.write_to_event_log(msg)

        # move build platform
        self.galil_thread = threading.Thread(
            target=self.move_build_platform, args=[position_settings, layer]
        )
        if not self.next_layer == 1:
            self.galil_thread.start()

        # do exposures
        exposure_data = {}
        for j, settings in enumerate(image_settings_list):
            self.exposure_worker(j, settings, exposure_data, msg)

        # log exposure data
        async_file_hander.write(self.exposure_log, f"layer {layer}:\n")
        for x in exposure_data:
            async_file_hander.write(
                self.exposure_log,
                f"{json.dumps({x: exposure_data[x]}, indent=2)}\n",
            )

    def pre_exposure_tasks(self, settings, light_engine):
        return

    def pre_exposure_joins(self, settings, light_engine):
        # wait for all hardware to be ready for exposure
        if not self.next_layer == 1:
            self.galil_thread.join()

    def exposure(self, settings, light_engine):
        return

    def get_le_status(self, settings, light_engine):
        return {}

    def post_exposure_tasks(self, msg):
        self.exposure_index += 1

        # update frontend message pane and progress bar
        msg = {
            "percent": int(100 * self.exposure_index / self.exposure_count),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "text": msg,
        }
        home.update_printer_state("print progress", msg)

    def exposure_worker(self, j, settings, exposure_data, msg):
        """Process a single exposure of the 3D print.

        This method should only be called from inside layer_worker.
        """
        # read settings for this exposure
        slices_folder = Path(self.print_settings["Header"]["Image directory"])
        self.image = self.current_job / slices_folder / Path(settings["Image file"])
        self.exposure_time_ms = settings["Layer exposure time (ms)"]
        self.power = settings["Light engine power setting"]
        layer_start_position = self.get_focus()
        light_engine = settings.get(
            "Light engine", config_dict["screen"]["light_engines"][0]
        )

        # run pre-exposure tasks
        self.write_to_event_log("Setup Exposure")
        self.pre_exposure_tasks(settings, light_engine)
        self.pre_exposure_joins(settings, light_engine)

        # do the exposure
        position_during_exposure = self.get_focus()
        pre_exposure_status = self.get_le_status(settings, light_engine)
        time.sleep(settings["Wait before exposure (ms)"] / 1000)
        self.write_to_event_log("Start Exposure")
        self.exposure(settings, light_engine)
        self.write_to_event_log("Finish Exposure")
        time.sleep(settings["Wait after exposure (ms)"] / 1000)

        self.post_exposure_tasks(msg)
        post_exposure_status = self.get_le_status(settings, light_engine)

        # save expoure data
        exposure_data[j] = {
            "image": self.image.name,
            "power setting": self.power,
            "exposure time (ms)": self.exposure_time_ms,
            "layer starting position": layer_start_position,
            "position during exposure": position_during_exposure,
            "post exposure position": self.get_focus(),
            "pre exposure status": pre_exposure_status,
            "post exposure status": post_exposure_status,
        }

    def finish_print(self):
        self.galil.logging_stop()
        self.galil.set_log_file(None)

        self.loadcell.stop()
        self.loadcell_running = False
        self.loadcell_thread = None
        home.clear_loadcell_graph()
        self.loadcell.set_log_file(None)

        # update fontend, zip logs into archive in print_history, and update db entrty
        self.print_duration = datetime.now() - self.print_start_time
        with self.app.app_context():
            latest_record = PrintRecord.query.order_by(PrintRecord.id.desc()).first()
            latest_record.end_time = datetime.now()
            if not self.printing_stopped.is_set():
                latest_record.completed = True
                self.state = "completed"
                msg = {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "text": f"Printing completed. Print took {self.print_duration}",
                }
                log.info(msg["text"])
                home.update_printer_state(self.state, msg)
                self.write_to_event_log(msg["text"])

            async_file_hander.finish()

            latest_record.save()
            shutil.make_archive(
                self.print_history / Path(latest_record.zip_filename[:-4]),
                "zip",
                self.current_job,
            )

    @property
    def isBusy(self):
        """boolean -- whether the printer is printing"""
        return self.print_thread.isAlive()

    def shutdown(self):
        if self.state not in ["busy", "printing"]:
            msg = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "text": "Shutting down",
            }
            log.info(msg["text"])
            home.update_printer_state("shutting down", msg)

            func = request.environ.get("werkzeug.server.shutdown")
            if func is None:
                raise RuntimeError("Not running with the Werkzeug Server")

            msg = "Shutdown completed"
            log.info(msg)
            home.update_printer_state(msg, dict())
            time.sleep(1)
            func()

        else:
            msg = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "text": "Don't try to shutdown 3D printer when it's busy",
            }
            log.warning(msg["text"])
            home.update_printer_state("shutdown failed", msg)

    def handle_upload(self, request):
        """Upload a print job.

        Grabs supplied files from the http request data, saves them to the
        upload folder on disk, and creates a new print job entry in the
        Print Queue table in the database.
        """

        for _, f in enumerate(request.files.getlist("file")):
            upload_time = datetime.now()
            filename_on_disk = os.path.join(
                Config.UPLOAD_FOLDER,
                "queue",
                f"{upload_time.strftime('job-%Y-%m-%d_%H-%M-%S.%f')}.zip",
            )
            f.save(filename_on_disk)
            if has_bad_metadata(filename_on_disk):
                log.debug("Removing hiden '__MACOSX' folder from %s ...", f.filename)
                clean_uploaded_file(filename_on_disk)
            try:
                _, schema_ver = validate_schema(filename_on_disk)
                if schema_ver not in config_dict["valid_schema_versions"]:
                    raise ValueError(f"Printer does not support {schema_ver} JSON format")
                log.info("Print job %s uploaded successfully.", f.filename)
                new_print_job = PrintQueue(
                    original_filename=f.filename,
                    upload_time=upload_time,
                    upload_ip=request.remote_addr,
                ).save()
                msg = {
                    "id": new_print_job.id,
                    "name": f.filename,
                    "upload_time": upload_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "upload_ip": request.remote_addr,
                }
                home.update_printer_state("job uploaded", msg)
            except ValueError as e:
                log.info("Job validation failed for %s", f.filename)
                msg = f"Job validation failed for {f.filename}:\n {str(e).strip()}"
                home.send_bootstrap_alert(msg)
                os.remove(filename_on_disk)

    def delete_job(self, message, delete_on_disk=True):
        """Delete a print job form the queue by removing it from the
        Print Queue table in the database and optionally deleting the print
        file stored on disk.

        If quiet flag is specified, don't try removing the print file from
        disk and don't notify the user via logging.
        """
        job_id = message["job"]
        job = PrintQueue.query.get_or_404(job_id)
        if delete_on_disk:
            try:
                os.remove(os.path.join(Config.UPLOAD_FOLDER, "queue", job.zip_filename))
            except FileNotFoundError:
                log.warning(
                    "The print file '%s' could not be found.", job.original_filename
                )
        msg = {
            "job": job_id,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "text": f"Print job '{job.original_filename}' deleted",
        }
        job.delete()
        if delete_on_disk:
            log.info(msg["text"])
        home.update_printer_state("job deleted", msg)
