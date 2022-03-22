import os
import time
import json
import shutil
import logging
import threading
import numpy as np
from PIL import Image
from pathlib import Path
from flask import request
from functools import wraps
from datetime import datetime
from zipfile import ZipFile, BadZipFile

import printer_server.views.home as home
from printer_server.extensions import db
from printer_server.settings import Config
from printer_server.models import PrintQueue, PrintRecord
from printer_server.print_file_validator import validate_v02
from printer_server.hardware_configuration import config_dict
from printer_server.async_file_handler import async_file_hander
from printer_server.hardware_configuration import driver_handles
from printer_server.views.manual_controls import get_last_calibration_positions
from printer_server.drivers.kdc101.kdc101_snip import get_kdc_positions
from printer_server.drivers.tiptilt.tiptilt_snip import get_tiptilt_positions


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def door_is_open(visitech_sticky_errors):
    """Return true if the door is open, else return false."""
    if "open" in visitech_sticky_errors.capitalize():
        return True
    return False


def get_last_focused_position():
    """Return the last focused position for the distance axis from the
    position log file.
    """
    return get_last_calibration_positions()["distance"]


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


def um_to_px(um):
    """Return the number of pixels corresponding to the length 'um' by
    rounding 'um' to the nearest 'pixel_pitch' increment.
    """
    pixel_pitch = 7.6
    return int(round(um / pixel_pitch))


def shift_image(img, x=0, y=0):
    """Shift the image by the specified number of pixels in x and y.
    Pixels that get shifted out of the image on one side disappear and
    the new pixels on the opposite side are copied from the original
    edge. This is accomplished by converting the image to a numpy array
    and building a list of row and column indicies to slice it with.
    """
    new_filename = img.parent / f"{img.stem}_shifted_{x}x_{y}y.png"
    img = np.array(Image.open(img))
    idx = [[], []]
    for axis, shift_by in enumerate((y, -x)):
        if shift_by > 0:
            idx[axis] = list(range(shift_by, img.shape[axis]))
            for _ in range(shift_by):
                idx[axis].append(img.shape[axis] - 1)
        elif shift_by < 0:
            idx[axis] = list(range(0, img.shape[axis] + shift_by))
            for _ in range(-shift_by):
                idx[axis].insert(0, 0)
    if idx[0]:
        img = img[idx[0], :]
    if idx[1]:
        img = img[:, idx[1]]
    img = Image.fromarray(img).convert("L")
    log.info("Saving new defocused image %s", new_filename)
    img.save(new_filename)
    return Path(new_filename)


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
            _thread = threading.Thread(target=func, args=(self, *args), kwargs={**kwargs})
            _thread.start()

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
        self.visitech = driver_handles.visitech
        self.kdc = driver_handles.kdc
        self.tiptilt = driver_handles.tiptilt
        self.loadcell = driver_handles.loadcell
        self.screen = driver_handles.screen

        # loadcell graph variables
        self.loadcell_running = False
        self.loadcell_thread = None

        # folders relevant to printing
        self.queue = Path(Config.UPLOAD_FOLDER) / Path("queue")
        self.current_job = Path(Config.UPLOAD_FOLDER) / Path("current_job")
        self.print_history = Path(Config.UPLOAD_FOLDER) / Path("print_history")

        # log files
        self.position_log = str(self.current_job / "position_data.csv")
        self.exposure_log = str(self.current_job / "exposure_data.txt")
        self.loadcell_log = str(self.current_job / "loadcell_data.csv")
        self.movement_log = str(self.current_job / "movement_data.csv")
        self.event_log = str(self.current_job / "event_log.csv")

        # values used during printing
        self.planarized_position = None
        self.focused_position = None
        self.print_position = None
        self.print_settings = None
        self.layer_map = []
        self.next_layer = 0
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
                f.extractall(self.current_job)
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
        log_data = self.print_settings.get("Header").get("Log data", True)
        async_file_hander.set_enabled(log_data)
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
            async_file_hander.write(self.movement_log, f"{a} status\n")
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

    def write_to_event_log(self, msg):
        async_file_hander.write(
            self.event_log, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')},{msg}\n"
        )

    def move_build_platform(self, position_settings, layer):
        """Perform the build platform movements for a layer according to
        the position_settings.
        """
        inital_wait = position_settings["Initial wait (ms)"] / 1000
        up_distance = position_settings["Distance up (mm)"]
        up_speed = position_settings["BP up speed (mm/sec)"]
        up_acceleration = position_settings["BP up acceleration (mm/sec^2)"]
        up_wait = position_settings["Up wait (ms)"] / 1000
        layer_thickness = position_settings["Layer thickness (um)"] / 1000
        down_speed = position_settings["BP down speed (mm/sec)"]
        down_acceleration = position_settings["BP down acceleration (mm/sec^2)"]
        final_wait = position_settings["Final wait (ms)"] / 1000

        time.sleep(inital_wait)
        start_position = self.galil.getPosition()
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        start_index = self.loadcell.get_current_loadcell_index()
        self.write_to_event_log("Start Up Movement")
        self.galil.absMove(
            mm=self.print_position - up_distance,
            speed=up_speed,
            acceleration=up_acceleration,
            wait_for_settling=False,
        )
        self.write_to_event_log("Finish Up Movement")
        time.sleep(up_wait)
        self.write_to_event_log("Start Down Movement")
        self.print_position -= layer_thickness
        self.galil.absMove(
            mm=self.print_position,
            speed=down_speed,
            acceleration=down_acceleration,
        )
        self.write_to_event_log("Finish Down Movement")

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
        use_relax_force = position_settings.get("Use relaxed force", True)
        relax_target = position_settings.get("Relaxed force (N)", 0)

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

        if use_relax_force:
            first_count = self.move_bp_to_force(relax_target + 5, speed=-0.5)
            second_count = self.move_bp_to_force(relax_target + 0.5, speed=-0.05)
            third_count = self.move_bp_to_force(relax_target, speed=-0.005)
            count = first_count + second_count + third_count

            log.info("Relax force reached %s steps", count)
            log.info("Relax force: %s", self.loadcell.get_current_force())
            log.info("Relax position: %s", self.galil.getPosition())
            if self.loadcell.get_current_force() < relax_target * 0.90:
                log.warning("Move_to_force overshot target value.")
        else:
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
                if len(forces) <= 10:
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
        return self.kdc.getCurrentPos()

    def change_focus(self, pos):
        self.write_to_event_log("Start Distance Movement")
        self.kdc.move(pos, relative=False)
        self.write_to_event_log("Finish Distance Movement")

    @run_in_thread("initialized", "Initialize")
    def initialize(self):
        """Put all hardware into starting configuration."""
        if self.state == "uninitialized":
            self.state = "busy"
            self.focused_position = get_last_focused_position()
            self.tiptilt.connect()
            self.loadcell.connect()

            kdc_thread = threading.Thread(target=self.kdc_setup_thread, args=[])
            galil_thread = threading.Thread(target=self.galil_setup_thread, args=[])
            screen_thread = threading.Thread(target=driver_handles.screen.start, args=[])
            visitech_thread = threading.Thread(target=self.visitech.connect, args=[])
            kdc_thread.start()
            galil_thread.start()
            screen_thread.start()
            visitech_thread.start()
            kdc_thread.join()
            galil_thread.join()
            screen_thread.join()
            visitech_thread.join()

            log.info("Printer initialized, all hardware ready.")

    def kdc_setup_thread(self):
        """Initialize and home ThorLabs stage"""
        self.kdc.connect()
        if not self.kdc.homed:
            self.kdc.home()
            self.kdc.move(self.focused_position, relative=False)

    def galil_setup_thread(self):
        """Initialize and home Galil controller"""
        self.galil.connect()
        self.galil.initialize()
        self.galil.home()
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
            log.debug(
                "Loadcell force (pre-step 1): %s", self.loadcell.get_current_force()
            )
            self.galil.goToZmin()
            target_force = config_dict["loadcell"]["loadcell_planarization_force"]
            if (
                self.move_bp_to_force(target_force, speed=2.5, error_threshold=0.75)
                is None
            ):
                log.error("Did not reach target planarization force.")
                return
            time.sleep(0.5)
            log.info(
                "Loadcell force (post-step 1): %s", self.loadcell.get_current_force()
            )

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
            target_force + 5, speed=-0.5, error_threshold=3.5
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
        with open(next(self.current_job.rglob("*.json")), "r") as file_handle:
            self.print_settings = json.load(file_handle)
        self.next_layer = 0

        # Start async_file_handler
        self.create_logs()

        position = get_kdc_positions()
        dist = position["distance"]
        self.write_to_event_log(f"Distance: {dist}")
        self.focused_position = float(position["distance"])

        position = get_tiptilt_positions()
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
            "percent": int(100 * (self.next_layer - 1) / len(self.layer_map)),
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

        # clear visitech overcurrent error
        self.visitech.get_sticky_errors(warn=False)
        self.suppress_visitech_ocp_error = True

        # generate layer map
        self.layer_map = self.generate_layer_map()

        # move build platform to the starting position if this is the first layer
        if self.next_layer == 0:
            self.galil.absMove(cnts=self.planarized_position)

        # iterate over layers
        for i, layer in enumerate(self.layer_map):
            if i < self.next_layer:
                continue  # skip previous layers if print was paused
            if self.printing_paused.is_set():
                self.loadcell.pause()
                break  # pause, don't do anything else
            if self.printing_stopped.is_set():
                break  # pause, don't do anything else
            self.next_layer = i + 1

            # process layer
            self.layer_worker(i, layer)

        # always turn off the Visitech
        self.visitech.stop_sequencer()
        home.update_led_status(False)
        self.screen.clear()

        # set paused position
        if self.printing_paused.is_set():
            self.paused_position = self.galil.getPosition()

        # move to top
        defaults_layer_settings = self.print_settings.get("Default layer settings")
        default_position_settings = defaults_layer_settings.get("Position settings")
        self.galil.absMove(
            mm=self.print_position - default_position_settings["Distance up (mm)"],
            speed=default_position_settings["BP up speed (mm/sec)"],
            acceleration=default_position_settings["BP up acceleration (mm/sec^2)"],
            wait_for_settling=False,
        )
        self.galil.goToZmax()
        time.sleep(1.0)

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
        galil_thread = threading.Thread(
            target=self.move_build_platform, args=[position_settings, layer]
        )
        if not self.next_layer == 1:
            galil_thread.start()

        # do exposures
        exposure_data = {}
        for j, settings in enumerate(image_settings_list):
            self.exposure_worker(j, settings, exposure_data, galil_thread)

        # log exposure data
        async_file_hander.write(self.exposure_log, f"layer {layer}:\n")
        for x in exposure_data:
            async_file_hander.write(
                self.exposure_log,
                f"{json.dumps({x: exposure_data[x]}, indent=2)}\n",
            )

        # update frontend message pane and progress bar
        msg = {
            "percent": int(100 * i / len(self.layer_map)),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "text": msg,
        }
        home.update_printer_state("print progress", msg)

    def exposure_worker(self, j, settings, exposure_data, galil_thread):
        """Process a single exposure of the 3D print.

        This method should only be called from inside layer_worker.
        """
        # read settings for this exposure
        slices_folder = Path(self.print_settings["Header"]["Image directory"])
        image = self.current_job / slices_folder / Path(settings["Image file"])
        exposure_time_ms = settings["Layer exposure time (ms)"]
        power = settings["Light engine power setting"]
        defocus_um = settings["Relative focus position (um)"]

        # defocus thread
        layer_start_position = self.get_focus()
        if defocus_um != 0:
            kdc_thread = threading.Thread(
                target=self.change_focus,
                args=[self.focused_position + defocus_um],
            )
            kdc_thread.start()
            image = shift_image(image, x=um_to_px(defocus_um))

        # screen thread
        screen_thread = threading.Thread(target=self.screen.draw, args=[image])
        screen_thread.start()

        # visitech setup thread
        self.write_to_event_log("Setup Exposure")
        visitech_thread = threading.Thread(
            target=self.visitech.setup_exposure, args=[exposure_time_ms, power]
        )
        visitech_thread.start()

        # wait for all hardware to be ready for exposure
        if defocus_um != 0:
            kdc_thread.join()
        if not self.next_layer == 1:
            galil_thread.join()
        screen_thread.join()
        visitech_thread.join()

        # do the exposure
        position_during_exposure = self.get_focus()
        pre_exposure_status = self.visitech.read_all_status()
        time.sleep(settings["Wait before exposure (ms)"] / 1000)
        self.write_to_event_log("Start Exposure")
        home.update_led_status(True)
        self.visitech.perform_exposure(exposure_time_ms)
        home.update_led_status(False)
        self.write_to_event_log("Finish Exposure")
        time.sleep(settings["Wait after exposure (ms)"] / 1000)

        # Suppress the first Visitech OCP error. This appears to always be
        # triggered on the first exposure of each print job. It would be better
        # to figure out why this happens in the hardware and fix it there.
        if self.suppress_visitech_ocp_error:
            self.suppress_visitech_ocp_error = False  # only do this once per print
            for e in self.visitech.get_sticky_errors(warn=False):
                if e and e.lower() != "led over current protection triggered":
                    log.warning("Visitech error: %s", e)  # report other errors
        post_exposure_status = self.visitech.read_all_status()

        # fix focus if this exposure was defocused
        if defocus_um != 0:
            self.change_focus(self.focused_position)

        # save expoure data
        exposure_data[j] = {
            "image": image.name,
            "power setting": power,
            "exposure time (ms)": exposure_time_ms,
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

        async_file_hander.finish()

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
                validate_v02(filename_on_disk)
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
