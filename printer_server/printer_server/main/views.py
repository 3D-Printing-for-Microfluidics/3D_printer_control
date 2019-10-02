# -*- coding: utf-8 -*-
"""Main view."""
import os
import shutil
# from flask import Blueprint, request, redirect, url_for, render_template
# from werkzeug.utils import secure_filename
from datetime import datetime
from zipfile import ZipFile
import glob
import time
from flask import Blueprint, request, render_template

from printer_server.settings import Config
from printer_server.hardware import printer3d, PrintSettings
from printer_server.threads import printingThreads
from printer_server.models import PrintJob, PrintRecord
from printer_server.extensions import socketio

blueprint = Blueprint('main', __name__, url_prefix='/', static_folder='../static')


@blueprint.route('/')
def index():
    allJobs = PrintJob.query.all()
    return render_template('index.html', allJobs=allJobs)


@socketio.on('connect', namespace='/printing')
def connect():
    socketio.emit(printer3d.state, dict(), namespace='/printing')


@socketio.on('initialize', namespace='/printing')
# pylint: disable=unused-argument
def initialize(message):
    if printer3d.state == 'uninitialized':
        printingThreads.initialize()


@socketio.on('planarization step 1', namespace='/printing')
# pylint: disable=unused-argument
def planarizationStep1(message):
    printer_states = ['initialized', 'planarized', 'completed', 'stopped']
    if printer3d.state in printer_states:
        printingThreads.planarizationStep1()


@socketio.on('planarization step 2', namespace='/printing')
# pylint: disable=unused-argument
def planarizationStep2(message):
    if printer3d.state is 'planarizing':
        printingThreads.planarizationStep2()


@socketio.on('start', namespace='/printing')
def start(message):
    if printer3d.state == 'planarized':
        jobId = message['job']

        if jobId:
            # Prepares and archive all the files and information needed for the print job
            job = PrintJob.query.get(jobId)
            if not job:
                return

            # Removes the `current_job` folder to get a fresh start
            try:
                shutil.rmtree(os.path.join(Config.UPLOAD_FOLDER, 'current_job'))
            except FileNotFoundError:
                pass
            except:
                pass

            _zipFile = os.path.join(Config.UPLOAD_FOLDER, 'queue', job.zip_filename)
            with ZipFile(_zipFile, 'r') as f:
                f.extractall(path=os.path.join(Config.UPLOAD_FOLDER, 'current_job'))
                # Removes hidden files from Mac
                try:
                    shutil.rmtree(os.path.join(Config.UPLOAD_FOLDER, 'current_job', '__MACOSX'))
                except FileNotFoundError:
                    pass

            # Moves the zip file in `queue` folder to `print_history` folder
            os.rename(_zipFile, os.path.join(Config.UPLOAD_FOLDER, 'print_history', job.zip_filename))

            # Saves a print record in the database
            printRecord = PrintRecord(original_filename=job.original_filename,
                                      upload_time=job.upload_time,
                                      upload_ip=job.upload_ip,
                                      start_ip=request.remote_addr)
            printRecord.save(commit=False)

            # Sends a `job selected` message to clients via sockets
            message = {
                'job': jobId,
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'text': 'Print Job ({}) selected'.format(job.original_filename)
            }
            # Once the job is selected and started, it will be deleted for queue.
            # Therefore, we can use the `job deleted` event here, but with a
            # different message.
            socketio.emit('job deleted', message,
                          namespace='/printing', broadcast=True)
            job.delete()

            printSettingsFile = glob.glob(os.path.join(Config.UPLOAD_FOLDER,
                                                       'current_job', '**/print_settings.json'),
                                          recursive=True)[0]
            printingThreads.printSettings = PrintSettings.fromFile(printSettingsFile)
            printingThreads.jsonDir = os.path.dirname(printSettingsFile)
            printingThreads.start()


@socketio.on('pause', namespace='/printing')
# pylint: disable=unused-argument
def pause(message):
    if printer3d.state is 'printing':
        printingThreads.pause()


@socketio.on('resume', namespace='/printing')
# pylint: disable=unused-argument
def resume(message):
    if printer3d.state is 'paused':
        printingThreads.resume()


@socketio.on('stop', namespace='/printing')
# pylint: disable=unused-argument
def stop(message):
    if printer3d.state is 'printing' or printer3d.state is 'paused':
        printingThreads.stop()


@socketio.on('shutdown', namespace='/printing')
def shutdown(message):
    if printer3d.state not in ['busy', 'printing']:
        message = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'text': 'Shutting down'
        }
        socketio.emit('shutting down', message,
                      namespace='/printing', broadcast=True)

        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')

        # printer3d.galil.__del__()     # TODO: use atexit here
        # printer3d.projector.__del__() # TODO: use atexit here

        socketio.emit('shutdown completed', dict(),
                      namespace='/printing', broadcast=True)
        time.sleep(1)
        func()

    else:
        message = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'text': "Try to shutdown 3D printer when it's busy"
        }
        socketio.emit('shutdown failed', message,
                      namespace='/printing', broadcast=True)
