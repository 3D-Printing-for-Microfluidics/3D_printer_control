import os
import time
import json
import shutil
import logging
import threading
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime
from functools import wraps
import numpy as np
from PIL import Image
from flask import Blueprint, request, render_template

from printer_server.settings import Config
from printer_server.hardware_configuration import hardware_driver_handles
from printer_server.print_file_validator import validate_v02
from printer_server.models import PrintQueue, PrintRecord
from printer_server.extensions import db, socketio

blueprint = Blueprint("home", __name__, url_prefix="/", static_folder="../static")
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
    log_file = Path(Config.PROJECT_ROOT) / "logs" / "calibration_position_log.txt"
    last_line = None
    with open(log_file) as f:
        for line in f:
            last_line = line.rstrip()
    for char in ["{", "}", ":", "'", ","]:
        last_line = last_line.replace(char, "")
    return float(last_line.split(" ")[-1])


def has_bad_metadata(filename):
    """Check to see if the zip file has a hidden __MACOSX folder."""
    with ZipFile(filename, "r") as input_file:
        for item in input_file.namelist():
            if item.startswith("__MACOSX/"):
                return True
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
                socketio.emit(self.state, dict(), namespace="/printing", broadcast=True)

            msg = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": text,
            }
            log.info(msg["text"])
            socketio.emit("busy", msg, namespace="/printing", broadcast=True)
            _thread = threading.Thread(
                target=func, args=(self, *args,), kwargs={**kwargs,}
            )
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
        self.galil = hardware_driver_handles.galil
        self.projector = hardware_driver_handles.projector
        self.kdc = hardware_driver_handles.kdc
        self.tiptilt = hardware_driver_handles.tiptilt
        self.loadcell = hardware_driver_handles.loadcell

        # folders relevant to printing
        self.queue = Path(Config.UPLOAD_FOLDER) / Path("queue")
        self.current_job = Path(Config.UPLOAD_FOLDER) / Path("current_job")
        self.print_history = Path(Config.UPLOAD_FOLDER) / Path("print_history")

        # values used during printing
        self.focused_position = None
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

    def get_num_duplications(self, layer):
        """Return the number of duplications for the layer.

        Overrides default value with a layer specific one if present.
        """
        d = self.print_settings.get("Default layer settings").get(
            "Number of duplications"
        )
        return layer.get("Number of duplications", d)

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

    def move_build_platform(self, position_settings):
        """Perform the build platform movements for a layer according to
        the position_settings.
        """
        time.sleep(position_settings["Initial wait (ms)"] / 1000)
        start_position = self.galil.getPosition()
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.galil.relMove(
            mm=-position_settings["Distance up (mm)"],
            speed=position_settings["BP up speed (mm/sec)"],
            acceleration=position_settings["BP up acceleration (mm/sec^2)"],
        )
        time.sleep(position_settings["Up wait (ms)"] / 1000)
        self.galil.relMove(
            mm=position_settings["Distance up (mm)"]
            - position_settings["Layer thickness (um)"] / 1000,
            speed=position_settings["BP up speed (mm/sec)"],
            acceleration=position_settings["BP up acceleration (mm/sec^2)"],
        )
        end_position = self.galil.getPosition()
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        time.sleep(position_settings["Final wait (ms)"] / 1000)
        thickness = self.galil.cntsToMm(abs(end_position - start_position) * 1000)
        return {
            "start time": start_time,
            "end time": end_time,
            "start position": start_position,
            "end position": end_position,
            "thickness (um)": thickness,
        }

    def perform_exposures(self, image_settings_list):
        """Perform all exposures for a layer according to
        image_settings_list.
        """
        slices_folder = Path(self.print_settings["Header"]["Image directory"])
        data = {}
        for i, settings in enumerate(image_settings_list):
            image = self.current_job / slices_folder / Path(settings["Image file"])
            exposure_time_ms = settings["Layer exposure time (ms)"]
            power = settings["Light engine power setting"]
            defocus_um = settings["Relative focus position (um)"]
            start_position = self.kdc.getCurrentPos()
            pre_exposure_status = self.projector.read_all_status()
            if defocus_um != 0:
                self.kdc.move(self.focused_position + defocus_um, relative=False)
                image = shift_image(image, x=um_to_px(defocus_um))
            time.sleep(settings["Wait before exposure (ms)"] / 1000)
            defocus_position = self.kdc.getCurrentPos()
            self.projector.project(image, exposure_time_ms, power)
            post_exposure_status = self.projector.read_all_status()
            time.sleep(settings["Wait after exposure (ms)"] / 1000)
            if defocus_um != 0:
                self.kdc.move(self.focused_position, relative=False)
            data[i] = {
                "pre exposure position": start_position,
                "defocused position": defocus_position,
                "post exposure position": self.kdc.getCurrentPos(),
                "pre exposure status": pre_exposure_status,
                "post exposure status": post_exposure_status,
            }
        if door_is_open(pre_exposure_status["led_sticky_errors"]):
            self.stop()
        if door_is_open(post_exposure_status["led_sticky_errors"]):
            self.stop()
        return data

    def connect(self):
        socketio.emit(self.state, dict(), namespace="/printing")

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
            projector_thread = threading.Thread(target=self.projector.connect, args=[])
            kdc_thread.start()
            galil_thread.start()
            projector_thread.start()
            kdc_thread.join()
            galil_thread.join()
            projector_thread.join()

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
        self.galil.motorOn()
        self.galil.home()
        self.galil.goToZmax()

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarizationStep1(self):
        """Lower build platform to lower position for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            self.state = "busy"
            self.loadcell.start()
            self.galil.goToZmin()

    @run_in_thread("planarized", "Planarization Step 2")
    def planarizationStep2(self):
        """Raise the build platform to begin printing."""
        if self.state == "planarizing":
            self.loadcell.get_current_force()
            pass

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
            self.paused_position = self.galil.getPosition()
            self.galil.goToZmax()

    # @run_in_thread("printing", "Resume Printing")
    def resume(self):
        """Resume a paused print."""
        if self.state != "paused":
            return
        log.info("Resuming print...")
        self.galil.absMove(cnts=self.paused_position)
        self.paused_position = None
        # update fontend
        msg = {
            "percent": int(100 * (self.next_layer - 1) / len(self.layer_map)),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": "Resume Printing",
        }
        self.state = "printing"
        log.info("Print resumed.")
        socketio.emit(self.state, msg, namespace="/printing", broadcast=True)
        # resume printing in a new thread
        app = db.get_app()
        self.print_thread = threading.Thread(target=self.print_worker, args=[app])
        self.print_thread.start()

    @run_in_thread("stopped", "Stop Printing")
    def stop(self):
        """Stop the printing process.

        This works almost the same as pause, except the 3D printer
        cannot resume and finish the previous print job.
        """
        if self.state in ["printing", "paused"]:
            log.info("Print stopped.")
            self.printing_stopped.set()
            self.print_thread.join()

    def start(self, job_id):
        """Do all preparatory work for a print, then start the printing
        process in a separate thread.

        The selected print job is retrieved from the Print Queue table
        in the database. The current_job folder is cleared and the job
        is extracted there. The original (still zipped) print file is
        also copied to the print_history folder. A new entry in the
        Print History table in the database is created for the current
        job, and it's entry in the Print Queue table is deleted. The
        print settings file is parsed and the settings saved, then the
        hardware operations are kicked off in a new thread.
        """
        if self.state != "planarized" or not job_id:
            return
        job_in_queue = PrintQueue.query.get(job_id)
        if not job_in_queue:
            return
        zipped_job_file = self.queue / Path(job_in_queue.zip_filename)

        # clear any old contents from the current_job folder
        try:
            shutil.rmtree(self.current_job)
        except FileNotFoundError:
            pass

        # extract to current_job
        with ZipFile(zipped_job_file, "r") as f:
            f.extractall(self.current_job)

        # create logs and overwrite any pre-existing data
        position_log = str(self.current_job / "position_data.txt")
        exposure_log = str(self.current_job / "exposure_data.txt")
        with open(position_log, "w") as f:
            f.write("")
        with open(exposure_log, "w") as f:
            f.write("")

        # move file from queue folder to print_history folder
        os.rename(zipped_job_file, self.print_history / Path(job_in_queue.zip_filename))

        # save job to Print History table in database
        print_history_entry = PrintRecord(
            original_filename=job_in_queue.original_filename,
            upload_time=job_in_queue.upload_time,
            upload_ip=job_in_queue.upload_ip,
            start_time=datetime.now(),
            start_ip=request.remote_addr,
        )
        print_history_entry.save(commit=False)

        # tell frontend to remove the job from the table and delete it from the database
        msg = {
            "job": job_id,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": f"Print Job ({job_in_queue.original_filename}) selected",
        }
        socketio.emit("job deleted", msg, namespace="/printing", broadcast=True)
        job_in_queue.delete()  # delete job from Print Queue table in database

        # parse and save print_settings
        with open(next(self.current_job.rglob("*.json")), "r") as file_handle:
            self.print_settings = json.load(file_handle)
        self.next_layer = 0

        # update frontend progress bar
        self.state = "printing"
        msg = {
            "percent": 0,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": "Start Printing",
        }
        log.info(msg["text"])
        socketio.emit(self.state, msg, namespace="/printing", broadcast=True)

        # start printing process in a new thread
        app = db.get_app()
        self.print_thread = threading.Thread(target=self.print_worker, args=[app])
        self.print_thread.start()

    def print_worker(self, app):
        """Do a 3D print.

        This method should not be called from the main thread since
        it will block the main thread until it is done and cannot be
        interrupted.

        :param app: The current flask app object. We have to get app in
                    the main thread, and pass it to the working thread
                    so we can use app_context to interact with the
                    database.
                    See http://flask-sqlalchemy.pocoo.org/contexts/.
        """
        if self.state != "printing":
            return
        # clear old flags
        self.printing_stopped.clear()
        self.printing_paused.clear()
        self.projector.get_sticky_errors(warn=False)
        self.layer_map = self.generate_layer_map()

        position_log = str(self.current_job / "position_data.txt")
        exposure_log = str(self.current_job / "exposure_data.txt")
        loadcell_log = str(self.current_job / "loadcell_data.txt")
        
        self.loadcell.set_log_file(loadcell_log)
        
        # move build platform to the starting position if this is the first layer
        if self.next_layer == 0:
            self.galil.goToZmin()

        # iterate over layers
        for i, layer in enumerate(self.layer_map):
            if i < self.next_layer:
                continue  # skip previous layers if print was paused
            if self.printing_paused.is_set() or self.printing_stopped.is_set():
                self.loadcell.pause()
                break  # pause, don't do anything else
            self.next_layer = i + 1

            # read settings for this layer
            current_layer_settings = self.print_settings["Layers"][layer[0]]
            position_settings = self.get_position_settings(current_layer_settings)
            image_settings_list = self.get_image_settings(current_layer_settings)

            # update log messages
            msg = f"Layer {layer[0]}-{layer[1]}" if layer[1] else f"Layer {layer[0]}"
            log.info(msg)

            # do moves and log data
            position_data = self.move_build_platform(position_settings)
            with open(position_log, "a") as f:
                f.write(f"layer {layer} data: {position_data}\n")

            # do exposures and log data
            exposure_data = self.perform_exposures(image_settings_list)
            with open(exposure_log, "a") as f:
                f.write(f"layer {layer} data: {exposure_data}\n")

            # update frontend message pane and progress bar
            socketio.emit(
                "print progress",
                {
                    "percent": int(100 * i / len(self.layer_map)),
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "text": msg,
                },
                namespace="/printing",
                broadcase=True,
            )

        # always turn off the projector
        self.projector.stop_sequencer()
        self.projector.clear_image()

        # if print is finished, move build platform back to top
        if not self.printing_paused.is_set():
            self.loadcell.stop()
            self.galil.goToZmax()

            # update fontend, zip logs into archive in print_history, and update db entrty
            with app.app_context():
                latest_record = PrintRecord.query.order_by(PrintRecord.id.desc()).first()
                latest_record.end_time = datetime.now()
                if not self.printing_stopped.is_set():
                    latest_record.completed = True
                    self.state = "completed"
                    msg = {
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "text": "Printing Compeleted",
                    }
                    log.info(msg["text"])
                    socketio.emit(self.state, msg, namespace="/printing", broadcast=True)
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
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": "Shutting down",
            }
            log.info(msg["text"])
            socketio.emit("shutting down", msg, namespace="/printing", broadcast=True)

            func = request.environ.get("werkzeug.server.shutdown")
            if func is None:
                raise RuntimeError("Not running with the Werkzeug Server")

            msg = "Shutdown completed"
            log.info(msg)
            socketio.emit(msg, dict(), namespace="/printing", broadcast=True)
            time.sleep(1)
            func()

        else:
            msg = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": "Don't try to shutdown 3D printer when it's busy",
            }
            log.warning(msg["text"])
            socketio.emit("shutdown failed", msg, namespace="/printing", broadcast=True)


print_control = PrintControl()


@blueprint.route("/")
def index():
    allJobs = PrintQueue.query.all()
    return render_template("home.html", allJobs=allJobs, hostname=Config.HOSTNAME)


@socketio.on("connect", namespace="/printing")
def connect():
    print_control.connect()


@socketio.on("initialize", namespace="/printing")
# pylint: disable=unused-argument
def initialize(message):
    print_control.initialize()


@socketio.on("planarization step 1", namespace="/printing")
# pylint: disable=unused-argument
def planarizationStep1(message):
    print_control.planarizationStep1()


@socketio.on("planarization step 2", namespace="/printing")
# pylint: disable=unused-argument
def planarizationStep2(message):
    print_control.planarizationStep2()


@socketio.on("start", namespace="/printing")
# pylint: disable=unused-argument
def start_print(message):
    print_control.start(message["job"])


@socketio.on("pause", namespace="/printing")
# pylint: disable=unused-argument
def pause_print(message):
    print_control.pause()


@socketio.on("resume", namespace="/printing")
# pylint: disable=unused-argument
def resume_print(message):
    print_control.resume()


@socketio.on("stop", namespace="/printing")
# pylint: disable=unused-argument
def stop(message):
    print_control.stop()


@socketio.on("shutdown", namespace="/printing")
# pylint: disable=unused-argument
def shutdown(message):
    print_control.shutdown()


@blueprint.route("handle-upload", methods=["POST"])
def handleUpload():
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
            socketio.emit(
                "job uploaded",
                {
                    "id": new_print_job.id,
                    "name": f.filename,
                    "upload_time": upload_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "upload_ip": request.remote_addr,
                },
                namespace="/printing",
                broadcast=True,
            )
        except ValueError as e:
            error_string = str(e).strip()
            msg = f"Job validation failed for {f.filename}:\n {error_string}"
            log.info("Job validation failed for %s: %s", f.filename, error_string)
            socketio.emit(
                "flash error", {"text": msg, "category": "danger"}, namespace="/printing",
            )
            os.remove(filename_on_disk)
    return ""


@socketio.on("delete job", namespace="/printing")
def deleteJob(message):
    """Delete a print job form the queue by removing it from the
    Print Queue table in the database.
    """
    job_id = message["job"]
    job = PrintQueue.query.get_or_404(job_id)
    os.remove(os.path.join(Config.UPLOAD_FOLDER, "queue", job.zip_filename))
    msg = {
        "job": job_id,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "text": f"Print Job ({job.original_filename}) deleted",
    }
    job.delete()
    log.info(msg["text"])
    socketio.emit("job deleted", msg, namespace="/printing", broadcast=True)
