# -*- coding: utf-8 -*-
"""Control view."""
import os
import shutil
from flask import Blueprint, request, redirect, url_for, render_template
from werkzeug.utils import secure_filename
from datetime import datetime
from zipfile import ZipFile
import glob
import time

from printer_server.settings import Config
from printer_server.hardware import printer3d, PrintSettings
from printer_server.threads import printingThreads
from printer_server.models import PrintJob, PrintRecord
from printer_server.extensions import socketio

blueprint = Blueprint('calibrate', __name__, url_prefix='/', static_folder='../static')


@blueprint.route('/calibrate')
def index():
    return render_template('calibrate.html')


@socketio.on('connect', namespace='/calibrate')
def connect():
    socketio.emit(printer3d.state, dict(), namespace='/calibrate')


@socketio.on('initialize', namespace='/calibrate')
def initialize(message):
    if printer3d.state is 'uninitialized':
        printingThreads.initialize()


@socketio.on('planarization step 1', namespace='/calibrate')
def planarizationStep1(message):
    printer_states = ['initialized', 'planarized', 'completed', 'stopped']
    if printer3d.state in printer_states:
        printingThreads.planarizationStep1()


@socketio.on('planarization step 2', namespace='/calibrate')
def planarizationStep2(message):
    if printer3d.state is 'planarizing':
        printingThreads.planarizationStep2()


@socketio.on('start', namespace='/calibrate')
def start(message):
    if printer3d.state is 'planarized':
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
                                      upload_time = job.upload_time,
                                      upload_ip = job.upload_ip,
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
                namespace='/calibrate', broadcast=True)
            job.delete()
            
            printSettingsFile = glob.glob(os.path.join(Config.UPLOAD_FOLDER, 
                'current_job', '**/print_settings.json'), recursive=True)[0]
            printingThreads.printSettings = PrintSettings.fromFile(printSettingsFile)
            printingThreads.jsonDir = os.path.dirname(printSettingsFile)
            printingThreads.start()


@socketio.on('pause', namespace='/calibrate')
def pause(message):
    if printer3d.state is 'printing':
        printingThreads.pause()


@socketio.on('resume', namespace='/calibrate')
def resume(message):
    if printer3d.state is 'paused':
        printingThreads.resume()


@socketio.on('stop', namespace='/calibrate')
def stop(message):
    if printer3d.state is 'printing' or printer3d.state is 'paused':
        printingThreads.stop()


@socketio.on('shutdown', namespace='/calibrate')
def shutdown(message):
    if printer3d.state not in ['busy', 'printing']:
        message = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'text': 'Shutting down'
        }
        socketio.emit('shutting down', message,
            namespace='/calibrate', broadcast=True)

        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
            
        printer3d.solus.__del__()
        printer3d.projector.__del__()
        
        socketio.emit('shutdown completed', dict(),
            namespace='/calibrate', broadcast=True)
        time.sleep(1)
        func()

    else:
        message = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'text': "Try to shutdown 3D printer when it's busy"
        }
        socketio.emit('shutdown failed', message,
            namespace='/calibrate', broadcast=True)


# @blueprint.route('print-history')
# def printHistroy():
#     page = request.args.get('page', 1, type=int)
    
#     _PR = PrintRecord
#     _q = _PR.query
    
#     try:
#         startDate = request.args.get('start', '')
#         if startDate:
#             temp =[int(i) for i in startDate.split('-')]
#             _startDate = datetime(*temp)
#             _q = _q.filter(_PR.start_time >= _startDate)
#     except ValueError:
#         flash('Incorrect start date', category='danger')
        
#     try:
#         endDate = request.args.get('end', '')
#         if endDate:
#             temp =[int(i) for i in endDate.split('-')]
#             _endDate = datetime(*temp)
#             _q = _q.filter(_PR.start_time <= _endDate)
#     except ValueError:
#         flash('Incorrect end date', category='danger')
        
#     recs = _q.order_by(_PR.id.desc()).paginate(page, 50)
#     startPage, endPage = calcPageNum(page, recs.pages)
#     return render_template('print_history.html', 
#                            recs=recs,
#                            startPage=startPage,
#                            endPage=endPage,
#                            startDate=startDate,
#                            endDate=endDate)
