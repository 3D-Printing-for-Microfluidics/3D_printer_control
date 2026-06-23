import os
import time
import json
import shutil
import signal
import logging
import threading
from pathlib import Path
from flask import request
from functools import wraps
from datetime import datetime
from zipfile import ZipFile, BadZipFile, ZIP_DEFLATED

import printer_server.views.home as home
from printer_server.settings import Config
from printer_server.threading_wrapper import Thread
from printer_server.models import PrintQueue, PrintRecord, Session
from printer_server.async_file_handler import async_file_hander
from printer_server.hardware_configuration.hardware_configuration import config_dict, driver_handles
from printer_server.print_file_validator import (
    validate_schema,
    read_json,
    expand_json,
    check_version,
    validate_printer_compatibility,
)
from printer_server.views.calibration import (
    get_last_calibration_positions_from_logs,
)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

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
                if top_level:
                    msg = {
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                        "text": text,
                    }
                    log.info(msg["text"])
                    home.update_printer_state("busy", msg)
                ret = f(self, *args, **kwargs)
                if top_level:
                    if ret == False:
                        self.state = "failed"
                    else:
                        self.state = state
                    home.update_printer_state(self.state, dict())
                return ret

            if run_in_thread:
                _thread = Thread(
                    log, name=f"print_control_({text})_thread", target=func, args=(self, *args), kwargs={**kwargs}
                )
                _thread.start()
            else:
                func(self, *args, **kwargs)

        return decorated_function

    return decorator

class PrintingException(Exception):
    pass

class PrintControl:
    """
    The PrintControl class contains all the 3D printer
    operations. It wraps the ``threading.Thread`` object such that
    a new thread is instantiated every time the 3D printer starts
    a long operation.
    """

    def __init__(self):
        self._state = "uninitialized"
        self.critical_error_handle = None

        # folders relevant to printing
        self.queue = Path(Config.UPLOAD_FOLDER) / Path("queue")
        self.current_job = Path(Config.UPLOAD_FOLDER) / Path("current_job")
        self.print_history = Path(Config.UPLOAD_FOLDER) / Path("print_history")

        # log files
        self.exposure_log = str(self.current_job / "logs" / "exposure_data.csv")
        self.event_log = str(self.current_job / "logs" / "event_log.csv")

        # threads
        self.bp_thread = None
        self.focus_thread = None
        self.xy_threads = None

        try:
            self.coord_systems = config_dict["coord_systems"]
        except:
            self.coord_systems = None

        # values used during printing
        self.image = None
        self.planarized_position = None
        self.focus = None
        self.tip = None
        self.tilt = None
        self.rotate = None
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
            "failed",
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
                    if (".csv" in name) or (".log" in name):
                        namelist.remove(name)
                f.extractall(self.current_job, members=namelist)
        except FileNotFoundError:
            self.delete_job({"job": job_id})
            return False
        except BadZipFile:
            log.warning("The print job with ID '%s' has a bad zip file.", job_id)
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
        design_metadata = self._get_design_metadata()
        print_history_entry = PrintRecord(
            original_filename=job.original_filename,
            upload_time=job.upload_time,
            upload_ip=job.upload_ip,
            user=Session.get_session_user(),
            session=Session.get_active_session(),
            start_time=datetime.now(),
            start_ip=request.remote_addr,
            **design_metadata,
        )
        print_history_entry.save(commit=False)

        # tell frontend to remove the job from the table and delete it from the database
        self.delete_job({"job": job_id}, delete_on_disk=False)

    def _get_design_metadata(self):
        try:
            json_path = next(self.current_job.rglob("*.json"))
            print_settings = read_json(json_path)
        except (StopIteration, FileNotFoundError, json.JSONDecodeError, OSError) as ex:
            log.info("Failed to read design metadata: %s", ex)
            return {}

        design = print_settings.get("Design") or {}
        return {
            "design_user": design.get("User"),
            "design_purpose": design.get("Purpose"),
            "design_description": design.get("Description"),
            "design_resin": design.get("Resin"),
            "design_printer": design.get("3D Printer"),
            "design_slicer": design.get("Slicer"),
            "design_slice_date": design.get("Date"),
        }

    def create_logs(self):
        # create logs and overwrite any pre-existing data
        try:
            os.mkdir(str(self.current_job / "logs"))
        except FileExistsError:
            pass
        
        async_file_hander.set_enabled(True)
        async_file_hander.write(self.exposure_log, "")
        async_file_hander.write(self.event_log, "timestamp,event\n")

        async_file_hander.write(self.exposure_log, f"layer,duplicate,exposure,setup time,start time,")
        async_file_hander.write(self.exposure_log, f"stop time,light engine,image name,power,exposure time,")
        async_file_hander.write(self.exposure_log, f"pre focus,focus,post focus,")
        async_file_hander.write(self.exposure_log, f"pre driver status,pre feedback,")
        async_file_hander.write(self.exposure_log, f"pre temp,pre driver temp,")
        async_file_hander.write(self.exposure_log, f"pre driver status2,pre feedback2,")
        async_file_hander.write(self.exposure_log, f"pre temp2,pre driver temp2,")
        async_file_hander.write(self.exposure_log, f"pre sticky errors,post driver status,")
        async_file_hander.write(self.exposure_log, f"post feedback,post temp,")
        async_file_hander.write(self.exposure_log, f"post driver temp,post driver status2,")
        async_file_hander.write(self.exposure_log, f"post feedback2,post temp2,")
        async_file_hander.write(self.exposure_log, f"post driver temp2,post sticky errors\n")

    def get_position_settings(self, layer):
        """Return the position settings for the layer."""
        d = self.print_settings.get("Default layer settings").get("Position settings")
        overrides = layer.get("Position settings")
        layer_settings = d.copy()
        if overrides is not None:
            layer_settings.update(overrides)
        return layer_settings

    def get_force_squeeze_settings(self, position_settings):
        """Return force squeeze settings for a layer.

        Supports v5 schema nesting under "Special layer techniques" -> "Squeeze out resin",
        while remaining backward-compatible with legacy flat keys.
        """
        special_settings = position_settings.get("Special layer techniques", {})
        force_squeeze_settings = special_settings.get("Squeeze out resin", {})
        if len(force_squeeze_settings) > 0:
            return force_squeeze_settings
        legacy_keys = {
            "Enable force squeeze",
            "Squeeze count",
            "Squeeze force (N)",
            "Squeeze wait (ms)",
        }
        if any(key in position_settings for key in legacy_keys):
            return position_settings
        return {}

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
    
    def _rotate_offsets(self, x_offset, y_offset, orientation):
        if orientation == "X":
            return x_offset, y_offset
        return -y_offset, x_offset

    def _rotate_offsets_inverse(self, x_offset, y_offset, orientation):
        if orientation == "X":
            return x_offset, y_offset
        return y_offset, -x_offset
    
    def xyf_adjustments_from_coord_system(self, coord_system_name, x, y, f, light_engine=None):
        '''
        Adjusts the x, y, and f offsets based on the coordinate system. This includes:
        1. Adjusting for alignment and stitching adjustments
        2. Rotating the offsets based on the orientation of the light engine
        3. Adding the coordinate system offsets

        Note: Focus adjustments based on stitching are only applied if direct focal measurements 
        are not available from the Keyence sensor, as determined by the config. This is because 
        if direct focal measurements are available, they should be more accurate than the stitching-based 
        adjustments.
        '''

        # validate coord_system_name
        if coord_system_name not in self.coord_systems:
            log.error("Invalid coordinate system name: '%s'", coord_system_name)
            return x, y, f
        
        direct_focus = "keyence" in config_dict.keys() and config_dict.get("keyence", {}).get("direct_focal_measurement", False)

        # adjust light engine coordinate system using le adjustments and stitching
        if coord_system_name in config_dict["light_engines"] or (direct_focus and coord_system_name == f"keyence_{light_engine}"):
            calibration_positions = get_last_calibration_positions_from_logs()
            tx = calibration_positions.get(f"{light_engine}_x_alignment", 0) / 1000
            ty = calibration_positions.get(f"{light_engine}_y_alignment", 0) / 1000
            a = calibration_positions.get(f"{light_engine}_x_shift_x", 0) / 1000
            b = calibration_positions.get(f"{light_engine}_x_shift_y", 0) / 1000
            c = calibration_positions.get(f"{light_engine}_y_shift_x", 0) / 1000
            d = calibration_positions.get(f"{light_engine}_y_shift_y", 0) / 1000
            p = calibration_positions.get(f"{light_engine}_focus_shift_x", 0) / 1000
            q = calibration_positions.get(f"{light_engine}_focus_shift_y", 0) / 1000

            _x = (1+a)*x + b*y + tx
            _y = c*x + (1+d)*y + ty

            # only use focus adjustments if direct measurements are not available
            if "keyence" not in config_dict.keys() or not config_dict.get("keyence", {}).get("direct_focal_measurement", True):
                _f = f + p*x + q*y
            else:
                _f = f
        else:
            _x = x
            _y = y
            _f = f

        _x, _y = self._rotate_offsets(
            _x, 
            _y, 
            config_dict[light_engine].get("orientation", "X"),
        )

        _x = _x + self.coord_systems[coord_system_name]["X"]
        _y = _y + self.coord_systems[coord_system_name]["Y"]
        _f = _f + self.coord_systems[coord_system_name].get("Focus", 0)

        return _x, _y, _f

    def xyf_adjustments_to_coord_system(self, coord_system_name, x, y, f, light_engine=None):
        '''
        Adjusts the x, y, and f offsets based on the coordinate system. This includes:
        1. Subtracting the coordinate system offsets
        2. Unrotating the offsets based on the orientation of the light engine
        3. Removing alignment and stitching adjustments
        '''

        # validate coord_system_name
        if coord_system_name not in self.coord_systems:
            log.error("Invalid coordinate system name: '%s'", coord_system_name)
            return x, y, f
        
        # transform offsets based on coordinate system
        _x = x - self.coord_systems[coord_system_name]["X"]
        _y = y - self.coord_systems[coord_system_name]["Y"]
        _f = f - self.coord_systems[coord_system_name].get("Focus", 0)

        _x, _y = self._rotate_offsets_inverse(
            _x, 
            _y, 
            config_dict[light_engine].get("orientation", "X"),
        )

        # if using direct focus, we also want to apply to f"keyence_{light_engine}" coord system
        direct_focus = "keyence" in config_dict.keys() and config_dict.get("keyence", {}).get("direct_focal_measurement", False)

        # adjust light engine coordinate system using le adjustments and stitching
        if coord_system_name in config_dict["light_engines"] or (direct_focus and coord_system_name == f"keyence_{light_engine}"):
            calibration_positions = get_last_calibration_positions_from_logs()
            tx = calibration_positions.get(f"{light_engine}_x_alignment", 0) / 1000
            ty = calibration_positions.get(f"{light_engine}_y_alignment", 0) / 1000
            a = calibration_positions.get(f"{light_engine}_x_shift_x", 0) / 1000
            b = calibration_positions.get(f"{light_engine}_x_shift_y", 0) / 1000
            c = calibration_positions.get(f"{light_engine}_y_shift_x", 0) / 1000
            d = calibration_positions.get(f"{light_engine}_y_shift_y", 0) / 1000
            p = calibration_positions.get(f"{light_engine}_focus_shift_x", 0) / 1000
            q = calibration_positions.get(f"{light_engine}_focus_shift_y", 0) / 1000
            det = (1+a)*(1+d) - b*c

            _x = ((1+d)*(_x - tx) - b*(_y - ty)) / det
            _y = (-c*(_x - tx) + (1+a)*(_y - ty)) / det
            if "keyence" not in config_dict.keys() or not config_dict.get("keyence", {}).get("direct_focal_measurement", True):
                _f = _f - p*_x - q*_y
        return _x, _y, _f

    def move_xyf_stages_in_coordinate_system(
            self, 
            coord_system_name=None, 
            x=None, 
            y=None, 
            f=None, 
            light_engine=None, 
            move_xy=True, 
            move_focus=True, 
            join=True
        ):
        '''Move the xy and focus stages based on the coordinate system adjustments. This includes:
        1. Adjusting the input x, y, and f values based on the coordinate system using xyf_adjustments_from_coord_system
        2. Moving the stages based on the adjusted values
        3. Optionally joining the threads and checking for exceptions
        '''
        
        _x, _y, _f = self.xyf_adjustments_from_coord_system(coord_system_name, x, y, f, light_engine=light_engine)

        _focus_thread = None
        if move_focus:
            log.debug("Moving focus stage to %s", _f)
            _focus_thread = self.focus_stage.threadedFocusMove(
                log, _f, join=False
            )
            time.sleep(0.05)
        _xy_threads = [None, None]
        if move_xy:
            _xy_threads = self.xy_stage.threadedXYMove(log, _x, _y, join=False)
        
        # Wait for moves to complete
        if join:
            for thread in _xy_threads:
                if thread is not None:
                    thread.join()
                    if thread.exception is not None:
                        log.critical("Unable to move xy stage")
                        self.failed_hardware["XY Stage"] = self.xy_stage
                        raise PrintingException()
            if _focus_thread is not None:
                _focus_thread.join()
                if _focus_thread.exception is not None:
                    log.critical("Unable to move focus stage")
                    self.failed_hardware["Focus Stage"] = self.focus_stage
                    raise PrintingException()
        else:
            _xy_threads.insert(0, _focus_thread)
            return _xy_threads
            
    def get_xyf_positions_in_coordinate_system(self, coord_system_name, light_engine=None):
        x, y = self.xy_stage.getXYPosition()
        f = self.focus_stage.getFocusPosition()
        return self.xyf_adjustments_to_coord_system(x, y, f, coord_system_name, light_engine=light_engine)

    def write_to_event_log(self, msg):
        async_file_hander.write(
            self.event_log, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')},{msg}\n"
        )

    def move_build_platform_up(self, position_settings):
        pass

    def move_build_platform_down(self, position_settings):
        pass

    def move_build_platform(self, position_settings, layer):
        pass
    
    def force_squeeze(self, position_settings, layer):
        log.warning("Missing loadcell_control. Cannot force_squeeze")
        return 0

    def get_focus(self):
        log.warning("Base printer_control class does not have a defined focus stage")
        return 0

    def convert_json_le_to_le(self, light_engine):
        # convert light engine to screen light engine
        le = None
        for temp in config_dict["light_engines"]:
            if temp in light_engine:
                le = temp
                break
        if le is None:
            log.error(
                "No matching light engine found in coord systems: '%s'", light_engine
            )
        return le

    @run_in_thread("initialized", "Initialize")
    def initialize(self, critical_error_handle):
        """Put all hardware into starting configuration."""
        if self.state == "uninitialized":
            # Create delete old profiles
            profile_enabled = Config.PROFILE_CODE
            if profile_enabled:
                profiles_dir = Path(Config.PROFILES_FOLDER)
                profile_file = str(Path(Config.PROJECT_ROOT) / "logs" / "profile.txt")
                if Path(profile_file).is_file():
                    os.remove(profile_file)
                if profiles_dir.is_dir():
                    shutil.rmtree(profiles_dir)
                    
            self.critical_error_handle = critical_error_handle
            self.state = "busy"
            self.failed_hardware = {}
            self.connect_hardware()
            return self._initialize()
        return False
    
    @run_in_thread("initialized", "Reinitialize")
    def reinitialize(self):
        threads = {}
        for name, device in self.failed_hardware.items():
            t = Thread(log, name=f"{name}_control_connect_thread", target=device.connect)
            t.start()
            threads[name] = t

        for name in list(self.failed_hardware.keys()):
            threads[name].join()
            device = self.failed_hardware[name]
            if not device.connected or threads[name].exception is not None:
                log.error("%s failed to connect!", name)
            else:
                del self.failed_hardware[name]
        return self._initialize()
    
    def _initialize(self):
        if len(self.failed_hardware.keys()) == 0:
            self.initialize_hardware()
            if len(self.failed_hardware.keys()) == 0:
                log.info("Printer initialized, all hardware ready.")
                home.play_sound("printer_ready.mp3")
                return True
        self.critical_error_handle(process = "initialization")
        return False
            
    def connect_hardware(self):
        pass

    def initialize_hardware(self):
        pass

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarization_step_1(self):
        """Lower the build platform for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            self.state = "busy"

            # sometimes the current_job and logs folder can get deleted during the print process (e.g. if the printer is restarted or if there is an error and the printer tries to clean up), so we need to recreate them if they are missing
            Path(self.current_job).mkdir(exist_ok=True)
            Path(self.current_job / "logs").mkdir(exist_ok=True)
            
            # Start async_file_handler
            async_file_hander.start()

    @run_in_thread("planarized", "Planarization Step 2")
    def planarization_step_2(self):
        self.print_position = self.planarized_position

    @run_in_thread("initialized", "Cancel Planarization")
    def cancel_planarization(self):
        async_file_hander.finish()

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

        # create logs
        self.create_logs()

        position = get_last_calibration_positions_from_logs()
        self.write_to_event_log(f"Calibration")
        for k, v in position.items():
            self.write_to_event_log(f"{k}: {v}")

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
        if check_version(self.print_settings) != "v999":
            self.print_thread = Thread(log, name="print_control_print_worker_thread", target=self.print_worker)
            self.print_thread.start()
        else:
            self.print_thread = Thread(log, name="print_control_test_worker_thread", target=self.test_worker)
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

    def get_vacuum_settings(self):
        """Return vacuum settings for a print.

        Supports v5 schema nesting under "Special print techniques" -> "Print under vacuum",
        while remaining backward-compatible with legacy Header keys.
        """
        special_print_techniques = self.print_settings.get("Special print techniques", {})
        vacuum_settings = special_print_techniques.get("Print under vacuum", {})
        if vacuum_settings:
            return vacuum_settings
        header = self.print_settings.get("Header", {})
        legacy_enable = header.get("Print under vacuum", False)
        return {"Enable vacuum": legacy_enable}

    def pre_print_tasks(self):
        return

    def pre_print_joins(self):
        return

    def post_print_tasks(self):
        return
    
    def post_print_joins(self):
        return
    
    def test_worker(self):
        return

    def print_worker(self):
        """Do a 3D print.

        This method should not be called from the main thread since
        it will block the main thread until it is done and cannot be
        interrupted.
        """
        if self.state != "printing":
            return

        # generate layer map
        self.layer_map = self.generate_layer_map()
        self.exposure_index = 0
        self.exposure_count = self.total_number_of_exposures()

        self.pre_print_tasks()
        self.pre_print_joins()

        # clear old flags
        self.printing_stopped.clear()
        self.printing_paused.clear()

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
            self.layer_worker(i, layer, msg)

        self.post_print_tasks()
        self.post_print_joins()

        # finish print
        if not self.printing_paused.is_set():
            self.finish_print()

    def pre_layer_tasks(self, i, layer):
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

    def pre_layer_joins(self):
        if not self.next_layer == 1:
            self.bp_thread.join()
            if self.bp_thread.exception is not None:
                raise self.bp_thread.exception

    def post_layer_tasks(self):
        return

    def layer_worker(self, i, layer, msg):
        """Process a single layer of the 3D print.

        This method should only be called from inside print_worker.
        """
        self.pre_layer_tasks(i, layer)
        self.pre_layer_joins()

        # read settings for this layer
        current_layer_settings = self.print_settings["Layers"][layer[0]]
        position_settings = self.get_position_settings(current_layer_settings)
        image_settings_list = self.get_image_settings(current_layer_settings)

        def split_print_on_film(exposures):
            film_exposures = []
            normal_exposures = []
            for exposure_settings in exposures:
                special_settings = exposure_settings.get("Special image techniques", {})
                film_settings = special_settings.get("Print on film", {})
                if film_settings.get("Enable print on film", False):
                    if len(film_exposures) == 0 and film_settings.get("Wait before exposure (ms)", 0) > exposure_settings.get("Wait before exposure (ms)", 0):
                        exposure_settings["Wait before exposure (ms)"] = film_settings.get("Wait before exposure (ms)", 0)
                    film_exposures.append(exposure_settings)
                else:
                    normal_exposures.append(exposure_settings)
            return film_exposures, normal_exposures

        def collect_zero_um_layers(exposures):
            zero_um_settings_list = []
            max_dups = 0
            for exposure_settings in exposures:
                special_settings = exposure_settings.get("Special image techniques", {})
                zero_um_settings = special_settings.get("0 um layer", {})
                if not zero_um_settings.get("Enable 0 um layer", False):
                    continue
                dup_count = int(zero_um_settings.get("Number of duplications", 1))
                dup_count = max(1, dup_count)
                max_dups = max(max_dups, dup_count)
                zero_um_settings_list.append((exposure_settings, dup_count))
            zero_um_layers = [[] for _ in range(max_dups)]
            for exposure_settings, dup_count in zero_um_settings_list:
                for dup_index in range(dup_count):
                    zero_um_layers[dup_index].append(exposure_settings)
            return zero_um_layers

        def run_exposures(exposures, layer_label, position_settings_override=None):
            if not exposures:
                return
            if self.printing_paused.is_set() or self.printing_stopped.is_set():
                return
            if position_settings_override is not None:
                self.move_build_platform(position_settings_override, layer)
            film_exposures, normal_exposures = split_print_on_film(exposures)
            film_offset = 0.0
            for j, exposure_settings in enumerate(film_exposures):
                if self.printing_paused.is_set() or self.printing_stopped.is_set():
                    return
                film_settings = exposure_settings.get("Special image techniques", {}).get("Print on film", {})
                target_offset = film_settings.get("Distance up (mm)", 0.3)
                delta = target_offset - film_offset
                if delta != 0:
                    film_position_settings = position_settings.copy()
                    film_position_settings["Distance up (mm)"] = abs(delta)
                    if delta > 0:
                        self.move_build_platform_up(film_position_settings)
                    else:
                        self.move_build_platform_down(film_position_settings)
                    film_offset = target_offset
                msg = f"{layer_label} Film Exposure {j}"
                log.info(msg)
                self.write_to_event_log(msg)
                self.exposure_worker(j, layer, exposure_settings, msg)

            if film_offset != 0:
                film_position_settings = position_settings.copy()
                film_position_settings["Distance up (mm)"] = abs(film_offset)
                self.move_build_platform_down(film_position_settings)

            for j, exposure_settings in enumerate(normal_exposures):
                if self.printing_paused.is_set() or self.printing_stopped.is_set():
                    return
                msg = f"{layer_label} Exposure {j}"
                log.info(msg)
                self.write_to_event_log(msg)
                self.exposure_worker(j, layer, exposure_settings, msg)

        layer_label = f"Layer {layer[0]}-{layer[1]}" if layer[1] else f"Layer {layer[0]}"
        run_exposures(image_settings_list, layer_label)

        zero_um_layers = collect_zero_um_layers(image_settings_list)
        if zero_um_layers:
            zero_position_settings = position_settings.copy()
            zero_position_settings["Layer thickness (um)"] = 0
            for dup_index, zero_layer_exposures in enumerate(zero_um_layers, start=1):
                if self.printing_paused.is_set() or self.printing_stopped.is_set():
                    return
                dup_label = f"{layer_label} 0um Dup {dup_index}"
                run_exposures(zero_layer_exposures, dup_label, position_settings_override=zero_position_settings)

    def get_exposure_defocus(self, settings, light_engine):
        return

    def pre_exposure_tasks(self, settings, light_engine):
        return

    def pre_exposure_joins(self, light_engine):
        return

    def exposure(self, settings, light_engine):
        return

    def get_le_status(self, settings, light_engine, warn="ALL"):
        return {}

    def post_exposure_tasks(self, light_engine, msg):
        self.exposure_index += 1

        # update frontend message pane and progress bar
        msg = {
            "percent": int(100 * self.exposure_index / self.exposure_count),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "text": msg,
        }
        home.update_printer_state("print progress", msg)

    def exposure_worker(self, j, layer, settings, msg):
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
            "Light engine", config_dict["light_engines"][0]
        )

        # run pre-exposure tasks
        setup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        self.write_to_event_log("Setup Exposure")
        self.pre_exposure_tasks(settings, light_engine)
        self.pre_exposure_joins(light_engine)

        # do the exposure
        position_during_exposure = self.get_focus()
        pre_exposure_status = self.get_le_status(settings, light_engine, warn="TEMP")
        time.sleep(settings["Wait before exposure (ms)"] / 1000)
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        self.write_to_event_log("Start Exposure")
        self.exposure(settings, light_engine)
        self.write_to_event_log("Finish Exposure")
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        time.sleep(settings["Wait after exposure (ms)"] / 1000)

        self.post_exposure_tasks(light_engine, msg)
        post_exposure_status = self.get_le_status(settings, light_engine, warn="ALL")

        # save expoure data
        async_file_hander.write(self.exposure_log, f"{layer[0]},{layer[1]},{j},{setup_time},{start_time},")
        async_file_hander.write(self.exposure_log, f"{end_time},{light_engine},{self.image.name},{self.power},{self.exposure_time_ms},")
        async_file_hander.write(self.exposure_log, f"{layer_start_position},{position_during_exposure},{self.get_focus()},")
        async_file_hander.write(self.exposure_log, f"{pre_exposure_status['led_driver_status']},{pre_exposure_status['led_feedback']},")
        async_file_hander.write(self.exposure_log, f"{pre_exposure_status['led_temp']},{pre_exposure_status['led_driver_temp']},")
        async_file_hander.write(self.exposure_log, f"{pre_exposure_status['led_driver_status2']},{pre_exposure_status['led_feedback2']},")
        async_file_hander.write(self.exposure_log, f"{pre_exposure_status['led_temp2']},{pre_exposure_status['led_driver_temp2']},")
        async_file_hander.write(self.exposure_log, f"{pre_exposure_status['led_sticky_errors']},{post_exposure_status['led_driver_status']},")
        async_file_hander.write(self.exposure_log, f"{post_exposure_status['led_feedback']},{post_exposure_status['led_temp']},")
        async_file_hander.write(self.exposure_log, f"{post_exposure_status['led_driver_temp']},{post_exposure_status['led_driver_status2']},")
        async_file_hander.write(self.exposure_log, f"{post_exposure_status['led_feedback2']},{post_exposure_status['led_temp2']},")
        async_file_hander.write(self.exposure_log, f"{post_exposure_status['led_driver_temp2']},{post_exposure_status['led_sticky_errors']}\n")


    def finish_print(self):
        # update fontend, zip logs into archive in print_history, and update db entrty
        self.print_duration = datetime.now() - self.print_start_time
        from autoapp import app
        with app.app_context():
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
                home.play_sound("print_finished.mp3")
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

    def shutdown(self, is_critical=True):
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
                os.kill(os.getpid(), signal.SIGKILL) 
                #SIGTERM hanging
                #SIGINT hanging
                #SIGKILL kills ssh as well?

        else:
            msg = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "text": "Don't try to shutdown 3D printer when it's busy",
            }
            log.warning(msg["text"])
            home.update_printer_state("shutdown failed", msg)


    def has_bad_metadata(self, filename):
        """Check to see if the zip file has a hidden __MACOSX folder."""
        try:
            with ZipFile(filename, "r") as input_file:
                for item in input_file.namelist():
                    if item.startswith("__MACOSX/"):
                        return True
            return False
        except BadZipFile:
            return False


    def clean_uploaded_file(self, filename):
        """Remove unwanted hidden files created by MAC OS in zipfiles."""
        temp_filename = Path(Config.UPLOAD_FOLDER) / "queue" / "temp.zip"
        with ZipFile(filename, "r") as old_file, ZipFile(temp_filename, "w", compression=ZIP_DEFLATED, compresslevel=6) as new_file:
            for item in old_file.infolist():
                buffer = old_file.read(item.filename)
                if not str(item.filename).startswith("__MACOSX/"):
                    new_file.writestr(item, buffer)
        shutil.move(temp_filename, filename)


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
            if self.has_bad_metadata(filename_on_disk):
                log.debug("Removing hiden '__MACOSX' folder from %s ...", f.filename)
                self.clean_uploaded_file(filename_on_disk)
            try:
                print_settings, schema_ver = validate_schema(filename_on_disk)
                if schema_ver not in config_dict["valid_schema_versions"]:
                    raise ValueError(f"Printer does not support {schema_ver} JSON format")
                validate_printer_compatibility(print_settings)
                


                log.info("Print job %s uploaded successfully.", f.filename)
                new_print_job = PrintQueue(
                    original_filename=f.filename,
                    upload_time=upload_time,
                    upload_ip=request.remote_addr,
                    user=Session.get_session_user()
                ).save()
                msg = {
                    "id": new_print_job.id,
                    "name": f.filename,
                    "upload_time": upload_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "upload_ip": request.remote_addr,
                    "user": Session.get_session_user().full_name if Session.get_session_user() else None,
                }
                home.update_printer_state("job uploaded", msg)
            except ValueError as ex:
                log.info("Job validation failed for %s", f.filename)
                msg = f"Job validation failed for {f.filename}:\n {str(ex).strip()}"
                home.send_bootstrap_alert(msg)
                os.remove(filename_on_disk)

    def delete_job(self, message, delete_on_disk=True):
        """Delete a print job from the queue by removing it from the
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
