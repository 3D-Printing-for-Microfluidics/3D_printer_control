# -*- coding: utf-8 -*-
"""Digital view."""
import os
from flask import Blueprint, request, render_template, flash
from datetime import datetime

from printer_server.settings import Config
from printer_server.config import printer3d, PrintSettings
from printer_server.models import PrintJob, PrintRecord
from printer_server.extensions import socketio
from printer_server.utils import calcPageNum

blueprint = Blueprint('digital', __name__, url_prefix='/', static_folder='../static')


@blueprint.route('handle-upload', methods=['POST'])
def handleUpload():
    form = request.form
    
    for i, file in enumerate(request.files.getlist('file')):
        uploadTime = datetime.now()
        newFilename = os.path.join(Config.UPLOAD_FOLDER, 'queue', 
            '{}.zip'.format(uploadTime.strftime('job-%Y-%m-%dT%H-%M-%S.%f')))
        file.save(newFilename)
    
        if not PrintSettings.validate(
            newFilename, 
            path=os.path.join(Config.UPLOAD_FOLDER, 'tmp')
            ):
            socketio.emit('my error',
                {'text': 'Job validation failed', 'category': 'danger'},
                namespace='/printing')
            os.remove(newFilename)
        else:
            newJob = PrintJob(original_filename=file.filename, 
                              upload_time=uploadTime, 
                              upload_ip=request.remote_addr).save()
            socketio.emit('job uploaded', 
                {'id': newJob.id,
                 'name': file.filename, 
                 'uploadTime': uploadTime.strftime("%Y-%m-%d %H:%M:%S"),
                 'uploadIP': request.remote_addr}, 
                 namespace='/printing', broadcast=True)
    return ''


@socketio.on('delete job', namespace='/printing')
def deleteJob(message):
    jobId = message['job']
    job = PrintJob.query.get_or_404(jobId)
    os.remove(os.path.join(Config.UPLOAD_FOLDER, 'queue', job.zip_filename))
    message = {
        'job': jobId,
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'text': 'Print Job ({}) Deleted'.format(job.original_filename)
    }
    job.delete()
    socketio.emit('job deleted', message, 
        namespace='/printing', broadcast=True)


@blueprint.route('print-history')
def printHistroy():
    page = request.args.get('page', 1, type=int)
    
    _PR = PrintRecord
    _q = _PR.query
    
    try:
        startDate = request.args.get('start', '')
        if startDate:
            temp =[int(i) for i in startDate.split('-')]
            _startDate = datetime(*temp)
            _q = _q.filter(_PR.start_time >= _startDate)
    except ValueError:
        flash('Incorrect start date', category='danger')
        
    try:
        endDate = request.args.get('end', '')
        if endDate:
            temp =[int(i) for i in endDate.split('-')]
            _endDate = datetime(*temp)
            _q = _q.filter(_PR.start_time <= _endDate)
    except ValueError:
        flash('Incorrect end date', category='danger')
        
    recs = _q.order_by(_PR.id.desc()).paginate(page, 50)
    startPage, endPage = calcPageNum(page, recs.pages)
    return render_template('print_history.html', 
                           recs=recs,
                           startPage=startPage,
                           endPage=endPage,
                           startDate=startDate,
                           endDate=endDate)



# TODO: add re-print feature























