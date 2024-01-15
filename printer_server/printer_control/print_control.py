import os
import time
import json
import shutil
import logging
import threading
from printer_server.threading_wrapper import Thread
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
from printer_server.hardware_configuration import config_dict, driver_handles
from printer_server.async_file_handler import async_file_hander
from printer_server.views.manual_controls import (
    get_last_calibration_positions_from_logs,
)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


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
        def decorated_function(self, *args, run_in_thread=False, top_level=False, **kwargs):
            run_in_thread = kwargs.get("run_in_thread", run_in_thread)
            top_level = kwargs.get("top_level", top_level)

            def func(self, *args, **kwargs):
                f(self, *args, **kwargs)
                if top_level:
                    self.state = state
                    home.update_printer_state(self.state, dict())

            if top_level:
                msg = {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "text": text,
                }
                log.info(msg["text"])
                home.update_printer_state("busy", msg)

            if run_in_thread:
                _thread = Thread(
                    log, name=f"print_control_'{text}'_thread", target=func, args=(self, *args), kwargs={**kwargs}
                )
                _thread.start()
            else:
                func(self, *args, **kwargs)

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

        # folders relevant to printing
        self.queue = Path(Config.UPLOAD_FOLDER) / Path("queue")
        self.current_job = Path(Config.UPLOAD_FOLDER) / Path("current_job")
        self.print_history = Path(Config.UPLOAD_FOLDER) / Path("print_history")

        # log files
        self.exposure_log = str(self.current_job / "exposure_data.log")
        self.event_log = str(self.current_job / "event_log.csv")

        # threads
        self.bp_thread = None
        self.focus_thread = None
        self.xy_threads = None

        self.coord_systems = None

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
            "shutting down"
        ]:
            self._state = state
        else:
            raise ValueError(f"Invalid state: {state}")

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
        async_file_hander.write(self.exposure_log, "")
        async_file_hander.write(self.event_log, "timestamp,event\n")

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

    def move_build_platform(self, position_settings, layer):
        log.warn("Base printer_control class does not have a defined bp stage. Cannot move bp")
        return 0

    def force_squeeze(self, position_settings, layer):
        log.warn("Missing loadcell_control. Cannot force_squeeze")
        return 0

    def get_focus(self):
        log.warn("Base printer_control class does not have a defined focus stage")
        return 0

    @run_in_thread("initialized", "Initialize")
    def initialize(self):
        """Put all hardware into starting configuration."""
        if self.state == "uninitialized":
            self.state = "busy"
            self.all_hardware_connected = True
            self.connect_hardware()
            if not self.all_hardware_connected:
                self.shutdown(is_critical=True)
                return False
            self.initalize_hardware()
            return True
        return False
            
    def connect_hardware(self):
        pass

    def initalize_hardware(self):
        pass

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self):
        """Lower the build platform for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            self.state = "busy"

    @run_in_thread("planarized", "Planarization Step 2")
    def planarization_step_2(self):
        self.print_position = self.planarized_position

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
        async_file_hander.start()

        position = get_last_calibration_positions_from_logs()
        self.write_to_event_log(f"Calibration: {position}")
        # dist = position["distance"]
        # self.write_to_event_log(f"Distance: {dist}")
        # tip = position["tip"]
        # self.write_to_event_log(f"Tip: {tip}")
        # tilt = position["tilt"]
        # self.write_to_event_log(f"Tilt: {tilt}")
        self.focused_position = float(position["distance"])

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
        self.print_thread = Thread(log, name="print_control_print_worker_thread", target=self.print_worker)
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
        self.print_thread = Thread(log, name="print_control_print_worker_thread", target=self.print_worker)
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

    def pre_print_joins(self):
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
        self.pre_print_joins()

        # update frontend message pane and progress bar
        msg = {
            "percent": int(100 * self.exposure_index / self.exposure_count),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }
        home.update_printer_state("print progress", msg)

        # iterate over layers
        for i, layer in enumerate(self.layer_map):
            if i < self.next_layer:
                self.exposure_index += self.exposures_in_layer(layer)
                continue  # skip previous layers if print was paused
            if self.printing_paused.is_set():
                break  # pause, don't do anything else
            if self.printing_stopped.is_set():
                break  # pause, don't do anything else
            self.next_layer = i + 1
            
            # update layer log messages
            msg = f"Layer {layer[0]}-{layer[1]}" if layer[1] else f"Layer {layer[0]}"
            log.info(msg)
            self.write_to_event_log(msg)

            # process layer
            self.layer_worker(i, layer)

        self.post_print_tasks()

        # finish print
        if not self.printing_paused.is_set():
            self.finish_print()

    def pre_layer_tasks(self, i, layer):
        return

    def pre_layer_joins(self):
        return

    def move_bp(self, settings, light_engine):
        return

    def post_layer_tasks(self):
        return

    def layer_worker(self, i, layer):
        """Process a single layer of the 3D print.

        This method should only be called from inside print_worker.
        """
        # read settings for this layer
        current_layer_settings = self.print_settings["Layers"][layer[0]]
        position_settings = self.get_position_settings(current_layer_settings)
        image_settings_list = self.get_image_settings(current_layer_settings)

        # move build platform
        self.bp_thread = Thread(
            log, name="print_control_move_bp_thread", target=self.move_build_platform, args=[position_settings, layer]
        )
        if not self.next_layer == 1:
            self.bp_thread.start()

        self.pre_layer_tasks(i, layer)
        self.pre_layer_joins()

        if not self.next_layer == 1:
            self.bp_thread.join()

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

    def get_exposure_defocus(self, settings, light_engine):
        return

    def pre_exposure_tasks(self, settings, light_engine):
        if type(self.focus_stage) is KDC101:
            self.image = shift_image(self.image, x=um_to_px(settings["Relative focus position (um)"]))
        return

    def pre_exposure_joins(self, light_engine):
        return

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
        self.pre_exposure_joins(light_engine)

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

    def shutdown(self, is_critical=False):
        if is_critical or self.state not in ["busy", "printing"]:
            if self.state not in ["shutting down", "shutdown completed"]:
                self.state = "shutting down"
                msg = {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "text": "Shutting down",
                }
                log.info(msg["text"])
                home.update_printer_state(self.state, msg)

                driver_handles.disconnect()

                time.sleep(0.5)

                msg = {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "text": "Shutdown completed",
                }
                log.info(msg["text"])
                home.update_printer_state("shutdown completed", msg)
                
                time.sleep(0.5)
                home.shutdown_handle()

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
