# -*- coding: utf-8 -*-
"""Main view."""

import os
import time
import glob
import json
import shutil
import threading
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, render_template

from printer_server.settings import Config
from printer_server.hardware_configuration import hardware_driver_handles

from printer_server.print_file_validator import validate_v02
from printer_server.models import PrintQueue, PrintRecord
from printer_server.extensions import db, socketio

blueprint = Blueprint("printing", __name__, url_prefix="/", static_folder="../static")
fmt = "%Y-%m-%d %H:%M:%S"


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

            # self.state = "busy"
            msg = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": text,
            }
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
        self.galil = hardware_driver_handles.galil
        self.projector = hardware_driver_handles.projector
        self.kdc = hardware_driver_handles.kdc
        self.tiptilt = hardware_driver_handles.tiptilt
        self.print_settings = None
        self.total_exposures = 0
        self.current_job = Path(Config.UPLOAD_FOLDER) / Path("current_job")
        self.print_history = Path(Config.UPLOAD_FOLDER) / Path("print_history")
        self.queue = Path(Config.UPLOAD_FOLDER) / Path("queue")
        self.printing_stopped = threading.Event()
        self.printing_paused = threading.Event()
        self.paused_layer = 1
        self.print_thread = None  # will be initialized later on start
        self.logs_path = Path.cwd() / "logs"
        self.logs_path_directory_for_this_run = None  # initialized later

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
        return final_settings

    def get_num_duplications(self, layer):
        """Return the number of duplications for the layer.

        Overrides default value with a layer specific one if present.
        """
        d = self.print_settings.get("Default layer settings").get(
            "Number of duplications"
        )
        return layer.get("Number of duplications", d)

    def get_total_exposures(self):
        """Return the total number of exposures in the print, including
        duplications.
        """
        default_dups = self.print_settings["Default layer settings"][
            "Number of duplications"
        ]
        total_layers = 0
        for layer in self.print_settings["Layers"]:
            total_layers += layer.get("Number of duplications", default_dups)
        return total_layers

    def move_build_platform(self, position_settings, i, j, layer_log, app):
        """Perform the build platform movements for a layer according to
        the position_settings.

        Append logged information to layer_log if supplied.
        """
        time.sleep(position_settings["Initial wait (ms)"] / 1000)
        start_position = self.galil.getPosition()
        start_time = datetime.now()
        self.galil.relMove(
            mm=position_settings["Distance up (mm)"],
            speed=position_settings["BP up speed (mm/sec)"],
            acceleration=position_settings["BP up acceleration (mm/sec^2)"],
        )
        time.sleep(position_settings["Up wait (ms)"] / 1000)
        self.galil.relMove(
            mm=position_settings["Layer thickness (um)"] / 1000
            - position_settings["Distance up (mm)"],
            speed=position_settings["BP up speed (mm/sec)"],
            acceleration=position_settings["BP up acceleration (mm/sec^2)"],
        )
        end_position = self.galil.getPosition()
        end_time = datetime.now()
        time.sleep(position_settings["Final wait (ms)"] / 1000)
        thickness = self.galil.cntsToMm(abs(end_position - start_position) * 1000)

        print(f"trying to open {layer_log}")
        with app.app_context():
            with open(layer_log, "a") as f:
                msg = f"Layer {i} duplicate {j} position data: "
                msg += f"start {start_position}, end {end_position}, "
                msg += f"thickness {thickness}, "
                msg += f"start_time {start_time}, end_time {end_time}, "
                msg += f"duration {end_time - start_time}\n"
                f.write(msg)

    def perform_exposures(self, image_settings_list, i, j, layer_log, app):
        """Perform all exposures for a layer according to
        image_settings_list.

        Append logged information to layer_log if supplied.
        """
        slices_folder = Path(self.print_settings["Header"]["Image directory"])
        for setting_index, settings in enumerate(image_settings_list):
            image = self.current_job / slices_folder / Path(settings["Image file"])
            exposure_time_ms = settings["Layer exposure time (ms)"]
            power = settings["Light engine power setting"]
            defocus_um = settings["Relative focus position (um)"]

            with app.app_context():
                with open(layer_log, "a") as f:
                    msg = f"Layer {i} duplicate {j} "
                    msg += f"exposure {setting_index} data: {settings}\n"
                    f.write(msg)

            if defocus_um != 0:
                self.kdc.move(defocus_um)
            time.sleep(settings["Wait before exposure (ms)"] / 1000)
            self.projector.project(image, exposure_time_ms, power)
            time.sleep(settings["Wait after exposure (ms)"] / 1000)
            if defocus_um != 0:
                self.kdc.move(-defocus_um)

    def connect(self):
        socketio.emit(self.state, dict(), namespace="/printing")

    @run_in_thread("initialized", "Initialize")
    def initialize(self):
        """Put all hardware into starting configuration."""
        if self.state == "uninitialized":
            self.tiptilt.connect()
            self.kdc.initialize()
            self.galil.connect()
            self.galil.motorOn()
            self.galil.home()
            self.galil.goToZmax()
            self.projector.connect()

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarizationStep1(self):
        """Lower build platform to lower position for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            self.galil.goToZmin()

    @run_in_thread("planarized", "Planarization Step 2")
    def planarizationStep2(self):
        """Raise the build platform to begin printing."""
        if self.state == "planarizing":
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

    @run_in_thread("stopped", "Stop Printing")
    def stop(self):
        """Stop the printing process.

        This works almost the same as pause, except the 3D printer
        cannot resume and finish the previous print job.
        """
        if self.state in ["printing", "paused"]:
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
        hardware operations are kicked off in a print_worker thread.
        """
        print("starting")
        if self.state != "planarized" or not job_id:
            return
        job_in_queue = PrintQueue.query.get(job_id)
        if not job_in_queue:
            return

        zipped_job_file = self.queue / Path(job_in_queue.zip_filename)

        try:
            shutil.rmtree(self.current_job)
        except FileNotFoundError:
            pass

        # extract to current_job
        with ZipFile(zipped_job_file, "r") as f:
            f.extractall(self.current_job)

        # move file from queue folder to print_history folder
        os.rename(zipped_job_file, self.print_history / Path(job_in_queue.zip_filename))

        # save job to Print History table in database
        print_history_entry = PrintRecord(
            original_filename=job_in_queue.original_filename,
            upload_time=job_in_queue.upload_time,
            upload_ip=job_in_queue.upload_ip,
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

        # update frontend progress bar
        self.state = "printing"
        msg = {
            "percent": 0,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": "Start Printing",
        }
        socketio.emit(self.state, msg, namespace="/printing", broadcast=True)

        app = db.get_app()
        self.print_thread = threading.Thread(target=self.print_worker, args=(1, app))
        print("starting thread")
        self.print_thread.start()

    def resume(self):
        """Resume a paused print.

        If printing is paused, this method starts printing from
        `paused_layer` in a new thread. When printing is completed,
        paused, or stopped, the thread ends gracefully.
        """
        if self.state != "paused":
            return
        self.state = "printing"
        msg = {
            "percent": int(100 * (self.paused_layer - 1) / self.total_exposures),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": "Resume Printing",
        }
        socketio.emit(self.state, msg, namespace="/printing", broadcast=True)

        app = db.get_app()
        self.print_thread = threading.Thread(
            target=self.print_worker, args=(self.paused_layer, app)
        )
        self.print_thread.start()

    def print_worker(self, start_on_layer, app):
        """Do a 3D print.

        This method should not be called from the main thread since
        it will block the main thread until it is done and cannot be
        interrupted.


        :param int start_on_layer: the layer to start printing from
        :param app: the current flask ``app`` object. We have to
                    get ``app`` in the main thread, and pass it
                    to the working thread. The reason that we need
                    ``app`` is that in order to interact with
                    database, we have to be under ``app_context``.
                    See http://flask-sqlalchemy.pocoo.org/contexts/.
        """

        print("got into print worker")
        if self.state != "printing":
            return
        # Initialize parameters
        self.printing_stopped.clear()
        self.printing_paused.clear()
        self.total_exposures = self.get_total_exposures()

        # Create logs
        layer_log = str(self.current_job / "layer_data.txt")
        load_cell_file_name = str(self.current_job / "load_cell_data.csv")

        import random

        with open(load_cell_file_name, "a") as f:
            for _ in range(100):
                r1 = random.randint(0, 1000)
                r2 = random.randint(0, 1000)
                r3 = random.randint(0, 1000)
                f.write(f"{r1}, {r2}, {r3}\n")

        # Move build platform to the starting position if this is the first layer
        if start_on_layer == 1:
            self.galil.goToZmin()

        # iterate over layers

        for i, current_layer in enumerate(self.print_settings["Layers"], 1):
            if self.printing_stopped.is_set() or self.printing_paused.is_set():
                self.paused_layer = i
                break

            # get to the desired layer
            # if i != start_on_layer:
            #     print(f"skip layer {i}")
            #     continue

            duplications = self.get_num_duplications(current_layer)
            image_settings_list = self.get_image_settings(current_layer)
            position_settings = self.get_position_settings(current_layer)

            for j in range(duplications):

                # self.move_build_platform(position_settings, layer_log, i, j, app)
                time.sleep(position_settings["Initial wait (ms)"] / 1000)
                start_position = self.galil.getPosition()
                start_time = datetime.now()
                self.galil.relMove(
                    mm=position_settings["Distance up (mm)"],
                    speed=position_settings["BP up speed (mm/sec)"],
                    acceleration=position_settings["BP up acceleration (mm/sec^2)"],
                )
                time.sleep(position_settings["Up wait (ms)"] / 1000)
                self.galil.relMove(
                    mm=position_settings["Layer thickness (um)"] / 1000
                    - position_settings["Distance up (mm)"],
                    speed=position_settings["BP up speed (mm/sec)"],
                    acceleration=position_settings["BP up acceleration (mm/sec^2)"],
                )
                end_position = self.galil.getPosition()
                end_time = datetime.now()
                time.sleep(position_settings["Final wait (ms)"] / 1000)
                thickness = self.galil.cntsToMm(abs(end_position - start_position) * 1000)

                with app.app_context():
                    with open(layer_log, "a") as f:
                        msg = f"Layer {i} duplicate {j} position data: "
                        msg += f"start {start_position}, end {end_position}, "
                        msg += f"thickness {thickness}, "
                        msg += f"start_time {start_time}, end_time {end_time}, "
                        msg += f"duration {end_time - start_time}\n"
                        f.write(msg)

                # self.perform_exposures(image_settings_list, layer_log, i, j, app)
                slices_folder = Path(self.print_settings["Header"]["Image directory"])
                for setting_index, settings in enumerate(image_settings_list):
                    image = (
                        self.current_job / slices_folder / Path(settings["Image file"])
                    )
                    exposure_time_ms = settings["Layer exposure time (ms)"]
                    power = settings["Light engine power setting"]
                    defocus_um = settings["Relative focus position (um)"]

                    with app.app_context():
                        with open(layer_log, "a") as f:
                            msg = f"Layer {i} duplicate {j} "
                            msg += f"exposure {setting_index} data: {settings}\n"
                            f.write(msg)

                    if defocus_um != 0:
                        self.kdc.move(defocus_um)
                    time.sleep(settings["Wait before exposure (ms)"] / 1000)
                    self.projector.project(image, exposure_time_ms, power)
                    time.sleep(settings["Wait after exposure (ms)"] / 1000)
                    if defocus_um != 0:
                        self.kdc.move(-defocus_um)

                socketio.emit(
                    "print progress",
                    {
                        "percent": int(100 * (i + j) / self.total_exposures),
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "text": f"Layer {i}",
                    },
                    namespace="/printing",
                    broadcase=True,
                )

        # Clean up
        self.projector.stop_sequencer()
        self.projector.clear_image()
        if not self.printing_paused.is_set():
            self.galil.goToZmax()
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
            socketio.emit("shutting down", msg, namespace="/printing", broadcast=True)

            func = request.environ.get("werkzeug.server.shutdown")
            if func is None:
                raise RuntimeError("Not running with the Werkzeug Server")

            socketio.emit(
                "shutdown completed", dict(), namespace="/printing", broadcast=True
            )
            time.sleep(1)
            func()

        else:
            msg = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": "Try to shutdown 3D printer when it's busy",
            }
            socketio.emit("shutdown failed", msg, namespace="/printing", broadcast=True)


print_control = PrintControl()


@blueprint.route("/")
def index():
    allJobs = PrintQueue.query.all()
    return render_template("printing.html", allJobs=allJobs)


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

        try:
            validate_v02(filename_on_disk)
            print(f"{f.filename} uploaded successfully.")
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
            msg = f"Job validation failed for {f.filename}:\n {str(e).strip()}"
            print(msg)
            socketio.emit(
                "validation error",
                {"text": msg, "category": "danger"},
                namespace="/printing",
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
        "text": f"Print Job ({job.original_filename}) Deleted",
    }
    job.delete()
    socketio.emit("job deleted", msg, namespace="/printing", broadcast=True)
