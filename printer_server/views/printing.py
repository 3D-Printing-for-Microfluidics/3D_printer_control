# -*- coding: utf-8 -*-
"""Main view."""

import os
import time
import glob
import shutil
import threading
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, render_template

from printer_server.settings import Config
from printer_server.hardware_configuration import hardware_driver_handles, PrintSettings

from printer_server.models import PrintJob, PrintRecord
from printer_server.extensions import db, socketio

blueprint = Blueprint("printing", __name__, url_prefix="/", static_folder="../static")


def run_in_thread(state, text):
    """Wrap the printer operation methods. The wrapped methods will push
    the 3D printer state changes to clients and finish their operations
    in another thread.

    :param str state: 3D printer state
    :param str text: printer message for the message box in webpage
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(self, *args, **kwargs):
            def func(self, *args, **kwargs):
                print("got into thread", self.state)
                f(self, *args, **kwargs)
                self.state = state
                socketio.emit(self.state, dict(), namespace="/printing", broadcast=True)

            # self.state = "busy"
            message = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": text,
            }
            socketio.emit("busy", message, namespace="/printing", broadcast=True)
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
    a long operation. This is because the native Python
    ``threading.Thread`` object can only be started once. With a wrapper
    class, we can retain all the useful information under the same
    namespace. This not only allows us to operate the 3D printer with a
    simple method call but also enables us to implement resuming
    printing very easily.

    .. py:attribute:: jsonDir

        the image path

    .. py:attribute:: printingStopped

        a ``threading.Event`` object to set flag to stop printing

    .. py:attribute:: printingPaused

        a ``threading.Event`` object to set flag to pause printing

    .. py:attribute:: pausedLayer

        the layer where the print is paused. If ``pausedLayer``
        is ``i``, it will start printing layer ``i`` after resume.

    """

    def __init__(self):
        self._state = "uninitialized"
        self.galil = hardware_driver_handles.galil
        self.projector = hardware_driver_handles.projector
        self.kdc = hardware_driver_handles.kdc
        self.tiptilt = hardware_driver_handles.tiptilt
        self.printSettings = None
        self.jsonDir = None
        self.printingStopped = threading.Event()
        self.printingPaused = threading.Event()
        self.pausedLayer = 1
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
            raise ValueError("Invalid state: {}".format(state))

    def calculateThickness(self, start, end):
        """ Helper funtion to calculate the layer thickness in um
        """
        return self.galil.cntsToMm(abs(end - start) * 1000)

    def connect(self):
        socketio.emit(self.state, dict(), namespace="/printing")

    @run_in_thread("initialized", "Initialize")
    def initialize(self):
        """Put all hardware into starting configuration."""
        print("TEST doing the init ", self.state)
        if self.state == "uninitialized":
            print("TEST really doing the init ")
            self.tiptilt.connect()
            self.kdc.initialize()
            self.galil.connect()
            self.galil.motorOn()
            self.galil.home()
            self.galil.goToZmax()
            self.projector.connect()

            # self.galil.openEncoderFile('encoder_initialization_write_file.txt')
            # self.galil.closeEncoderFile()

    @run_in_thread("planarizing", "Planarization Step 1")
    def planarizationStep1(self):
        """Lower build platform to lower position for planarization."""
        if self.state in ["initialized", "planarized", "completed", "stopped"]:
            # print("Planarization Step 1")
            # self.galil.openEncoderFile('encoder_planarization_write_file.txt')
            self.galil.goToZmin()
            # self.galil.closeEncoderFile()

    @run_in_thread("planarized", "Planarization Step 2")
    def planarizationStep2(self):
        """Raise the build platform to begin printing."""
        if self.state is "planarizing":
            # self.galil.goToZmax()
            # self.galil.goToPlanarizationPullOff()
            pass

    @run_in_thread("paused", "Pause Printing")
    def pause(self):
        """Pause the printing process. It is implemented with a
        ``threading.Event`` object, :py:attr:`printingPaused`.
        The :py:meth:`printingPaused.is_set()` is only checked at
        the beginning of every layer. If ``True``, the printing
        will be paused. If the operations of a layer have started,
        the 3D printer will finish that layer first. After being
        paused, the 3D printer can resume and continue finishing
        the print job.
        """
        if self.state == "printing":
            self.printingPaused.set()
            self.print_thread.join()

    @run_in_thread("stopped", "Stop Printing")
    def stop(self):
        """Stop the printing process. It works basically the same
        as :py:meth:`pause`, except the 3D printer can not resume
        and finish the previous print job.
        """
        if self.state in ["printing", "paused"]:
            self.printingStopped.set()
            self.print_thread.join()
            # self.galil.closeEncoderFile()
            # self.galil.closeLoadCellFile()

    def start(self, job_id):
        """This method starts a new print.

        If printer is planarized, this method starts printing from
        layer 1 in a new thread. When printing is completed, paused,
        or stopped, the thread ends gracefully.
        """
        if self.state != "planarized" or not job_id:
            return

        # Prepares and archive all the files and information needed for the print job
        job = PrintJob.query.get(job_id)
        if not job:
            return

        # Removes the `current_job` folder to get a fresh start
        try:
            shutil.rmtree(os.path.join(Config.UPLOAD_FOLDER, "current_job"))
        except FileNotFoundError:
            pass
        # except:
        #     pass

        _zipFile = os.path.join(Config.UPLOAD_FOLDER, "queue", job.zip_filename)
        with ZipFile(_zipFile, "r") as f:
            f.extractall(path=os.path.join(Config.UPLOAD_FOLDER, "current_job"))
            # Removes hidden files from Mac
            try:
                shutil.rmtree(
                    os.path.join(Config.UPLOAD_FOLDER, "current_job", "__MACOSX")
                )
            except FileNotFoundError:
                pass

        # Moves the zip file in `queue` folder to `print_history` folder
        os.rename(
            _zipFile,
            os.path.join(Config.UPLOAD_FOLDER, "print_history", job.zip_filename),
        )

        # Saves a print record in the database
        printRecord = PrintRecord(
            original_filename=job.original_filename,
            upload_time=job.upload_time,
            upload_ip=job.upload_ip,
            start_ip=request.remote_addr,
        )
        printRecord.save(commit=False)

        # Sends a `job selected` message to clients via sockets
        message = {
            "job": job_id,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": "Print Job ({}) selected".format(job.original_filename),
        }
        # Once the job is selected and started, it will be deleted for queue.
        # Therefore, we can use the `job deleted` event here, but with a
        # different message.
        socketio.emit("job deleted", message, namespace="/printing", broadcast=True)
        job.delete()

        printSettingsFile = glob.glob(
            os.path.join(Config.UPLOAD_FOLDER, "current_job", "**/print_settings.json"),
            recursive=True,
        )[0]
        self.printSettings = PrintSettings.fromFile(printSettingsFile)
        self.jsonDir = os.path.dirname(printSettingsFile)

        self.state = "printing"
        message = {
            "percent": 0,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": "Start Printing",
        }
        socketio.emit(self.state, message, namespace="/printing", broadcast=True)

        app = db.get_app()
        self.print_thread = threading.Thread(target=self.print_worker, args=(1, app))
        self.print_thread.start()

    def resume(self):
        """This method resumes a paused print.

        If printing is paused, this method starts printing from
        :py:attr:`pausedLayer` in a new thread. When printing is
        completed, paused, or stopped, the thread ends gracefully.
        """
        if self.state != "paused":
            return
        self.state = "printing"
        message = {
            "percent": int(
                100 * (self.pausedLayer - 1) / self.printSettings.totalLayerNum
            ),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": "Resume Printing",
        }
        socketio.emit(self.state, message, namespace="/printing", broadcast=True)

        app = db.get_app()
        self.print_thread = threading.Thread(
            target=self.print_worker, args=(self.pausedLayer, app)
        )
        self.print_thread.start()

    def print_worker(self, startingLayer, app):
        """The ``print_worker`` method implements the printing
        process.

        .. note::
            This method should **NEVER** be called from the main
            thread. Otherwise, it will block the main thread until
            it is done, and cannot be interrupted.

        .. describe:: Printing process

        #. It starts with initializing parameters.
        #. Then the build platform move to the starting height.
        #. The layers will be iterated from the starting layer to
           the last.

            #. Every layer starts with checking whether printing
               is stopped or paused.
            #. If not, it goes through the mechanical operations
               in Galil first, and then exposes the layer with
               all the images.

        #. If the printing is stopped, paused, or completed, it
           exits the for-loop, cleans up, and ends gracefully.

            #. If printing is paused, the current layer number
               will be saved to :py:attr:`pausedLayer`, and the
               build platform will move up 30 mm and wait for
               further instruction.
            #. If printing is stopped, the build platform will
               move up to home position.

        :param int startingLayer: the layer to start printing
        :param app: the current flask ``app`` object. We have to
                    get ``app`` in the main thread, and pass it
                    to the working thread. The reason that we need
                    ``app`` is that in order to interact with
                    database, we have to be under ``app_context``.
                    See http://flask-sqlalchemy.pocoo.org/contexts/.
        """
        # Initialize parameters
        self.printingStopped.clear()
        self.printingPaused.clear()

        # Create log
        date_and_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.logs_path_directory_for_this_run = self.logs_path / date_and_time
        self.logs_path_directory_for_this_run.mkdir()
        encoder_print_file_name = str(
            self.logs_path_directory_for_this_run / "encoder_print_file.txt"
        )
        # load_cell_file_name = self.logs_path_directory_for_this_run / 'load_cell_print_file.txt'

        # Move build platform to the starting position
        if startingLayer == 1:
            start, end, start_time, end_time = self.galil.printCycle(
                self.printSettings.getLayerThicknessMm(1),
                self.printSettings.getCommandChain(1),
            )
            with open(encoder_print_file_name, "a") as f:
                f.write(
                    "Layer {}: start {}, end {}, thickness {}, time {}, duration {}\n".format(
                        1,
                        start,
                        end,
                        self.calculateThickness(start, end),
                        datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                        end_time - start_time,
                    )
                )
        else:
            self.galil.resume(self.printSettings.getLayerThicknessMm(startingLayer))

        # Iterate from the startingLayer to the last
        totalLayerNum = self.printSettings.totalLayerNum
        for i in range(startingLayer, totalLayerNum + 1):
            if self.printingStopped.is_set() or self.printingPaused.is_set():
                self.pausedLayer = i  # layer i has not been exposed
                break

            # self.galil.encoder_print_file.write("Layer %d \r\n" %(i))
            if i != startingLayer:
                start, end, start_time, end_time = self.galil.printCycle(
                    self.printSettings.getLayerThicknessMm(i),
                    self.printSettings.getCommandChain(i),
                )
                with open(encoder_print_file_name, "a") as f:
                    f.write(
                        "Layer {}: start {}, end {}, thickness {}, time {}, duration {}\n".format(
                            i,
                            start,
                            end,
                            self.calculateThickness(start, end),
                            datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                            end_time - start_time,
                        )
                    )

            images = [
                os.path.join(self.jsonDir, im) for im in self.printSettings.getImages(i)
            ]

            self.projector.projectMulti(
                images,
                self.printSettings.getExposureTimeMs(i),
                self.printSettings.getLedPowers(i),
            )

            socketio.emit(
                "print progress",
                {
                    "percent": int(100 * i / totalLayerNum),
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "text": "Layer {}".format(i),
                },
                namespace="/printing",
                broadcase=True,
            )

        # Clean up
        # self.galil.stopLoadCell()
        self.projector.stop_sequencer()
        self.projector.clear_image()
        if self.printingPaused.is_set():
            self.galil.pause()
        else:
            self.galil.goToZmax()

            # save the end time to database
            with app.app_context():
                latestPrintRecord = PrintRecord.query.order_by(
                    PrintRecord.id.desc()
                ).first()
                latestPrintRecord.end_time = datetime.now()
                if self.printingStopped.is_set():
                    latestPrintRecord.completed = False
                latestPrintRecord.save()

            if not self.printingStopped.is_set() and not self.printingPaused.is_set():
                self.state = "completed"
                message = {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "text": "Printing Compeleted",
                }
                socketio.emit(
                    self.state, message, namespace="/printing", broadcast=True,
                )
        # self.galil.closeEncoderFile()
        # self.galil.closeLoadCellFile()

    @property
    def isBusy(self):
        """boolean -- whether the printer is printing"""
        return self.print_thread.isAlive()

    def shutdown(self):
        if self.state not in ["busy", "printing"]:
            message = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": "Shutting down",
            }
            socketio.emit("shutting down", message, namespace="/printing", broadcast=True)

            func = request.environ.get("werkzeug.server.shutdown")
            if func is None:
                raise RuntimeError("Not running with the Werkzeug Server")

            socketio.emit(
                "shutdown completed", dict(), namespace="/printing", broadcast=True
            )
            time.sleep(1)
            func()

        else:
            message = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": "Try to shutdown 3D printer when it's busy",
            }
            socketio.emit(
                "shutdown failed", message, namespace="/printing", broadcast=True
            )


printControl = PrintControl()


@blueprint.route("/")
def index():
    allJobs = PrintJob.query.all()
    return render_template("printing.html", allJobs=allJobs)


@socketio.on("connect", namespace="/printing")
def connect():
    printControl.connect()


@socketio.on("initialize", namespace="/printing")
# pylint: disable=unused-argument
def initialize(message):
    printControl.initialize()


@socketio.on("planarization step 1", namespace="/printing")
# pylint: disable=unused-argument
def planarizationStep1(message):
    printControl.planarizationStep1()


@socketio.on("planarization step 2", namespace="/printing")
# pylint: disable=unused-argument
def planarizationStep2(message):
    printControl.planarizationStep2()


@socketio.on("start", namespace="/printing")
# pylint: disable=unused-argument
def start_print(message):
    printControl.start(message["job"])


@socketio.on("pause", namespace="/printing")
# pylint: disable=unused-argument
def pause_print(message):
    printControl.pause()


@socketio.on("resume", namespace="/printing")
# pylint: disable=unused-argument
def resume_print(message):
    printControl.resume()


@socketio.on("stop", namespace="/printing")
# pylint: disable=unused-argument
def stop(message):
    printControl.stop()


@socketio.on("shutdown", namespace="/printing")
# pylint: disable=unused-argument
def shutdown(message):
    printControl.shutdown()


@blueprint.route("handle-upload", methods=["POST"])
def handleUpload():
    for _, file in enumerate(request.files.getlist("file")):
        uploadTime = datetime.now()
        newFilename = os.path.join(
            Config.UPLOAD_FOLDER,
            "queue",
            "{}.zip".format(uploadTime.strftime("job-%Y-%m-%dT%H-%M-%S.%f")),
        )
        file.save(newFilename)

        if not PrintSettings.validate(
            newFilename, path=os.path.join(Config.UPLOAD_FOLDER, "tmp")
        ):
            socketio.emit(
                "my error",
                {"text": "Job validation failed wow", "category": "danger"},
                namespace="/printing",
            )
            os.remove(newFilename)
        else:
            newJob = PrintJob(
                original_filename=file.filename,
                upload_time=uploadTime,
                upload_ip=request.remote_addr,
            ).save()
            socketio.emit(
                "job uploaded",
                {
                    "id": newJob.id,
                    "name": file.filename,
                    "uploadTime": uploadTime.strftime("%Y-%m-%d %H:%M:%S"),
                    "uploadIP": request.remote_addr,
                },
                namespace="/printing",
                broadcast=True,
            )
    return ""


@socketio.on("delete job", namespace="/printing")
def deleteJob(message):
    job_id = message["job"]
    job = PrintJob.query.get_or_404(job_id)
    os.remove(os.path.join(Config.UPLOAD_FOLDER, "queue", job.zip_filename))
    message = {
        "job": job_id,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "text": "Print Job ({}) Deleted".format(job.original_filename),
    }
    job.delete()
    socketio.emit("job deleted", message, namespace="/printing", broadcast=True)
