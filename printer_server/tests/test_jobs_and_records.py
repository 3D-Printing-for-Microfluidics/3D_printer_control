# -*- coding: utf-8 -*-
"""Test print jobs and records."""
import pytest
from flask import url_for
import os
from datetime import datetime
import glob
import time
import io
import shutil

from printer_server.settings import Config
from printer_server.models import PrintJob
from .factories import PrintRecordFactory


@pytest.mark.usefixtures('client_class', 'db')
class TestUpload:

    def test_can_upload(self):
        testFile = os.path.join(Config.PROJECT_ROOT, 'tests', 
                                'dummy_files', 'zipfiles', 'correct_job.zip')
        content = open(testFile, 'rb').read()
        res = self.client.post(url_for('digital.handleUpload'),
            data=dict(file=(io.BytesIO(content), 'correct_job.zip')))
        assert res.status_code == 200
        
        # Test PrintJob saved to database
        job = PrintJob.query.filter_by(original_filename='correct_job.zip').first()
        assert bool(job)
        
        filename = os.path.join(Config.UPLOAD_FOLDER, 'queue',
            '{}*.zip'.format(datetime.now().strftime('job-%Y-%m-%dT%H-%M')))
        fileUploaded = glob.glob(filename)[0]
        os.remove(fileUploaded)
        
    def test_warning_when_upload_bad_job_file(self):
        testFile = os.path.join(Config.PROJECT_ROOT, 'tests', 
                                'dummy_files', 'zipfiles', 'corrupted.zip')
        content = open(testFile, 'rb').read()
        res = self.client.post(url_for('digital.handleUpload'),
            data=dict(file=(io.BytesIO(content), 'corrupted.zip')))
        assert res.status_code == 200
        job = PrintJob.query.filter_by(original_filename='corrupted.zip').first()
        assert not bool(job)


class TestDeletingPrintJob:
    
    def test_delete_print_job(self, printjob, socketio_client):
        socketio_client.get_received(namespace='/printing')
        socketio_client.emit('delete job', 
                             {'job': str(printjob.id)}, 
                             namespace='/printing')
        
        received = socketio_client.get_received(namespace='/printing')
        assert len(received) == 1
        assert len(received[0]['args']) == 1
        assert received[0]['name'] == 'job deleted'
        message = received[0]['args'][0]
        assert message['job'] == str(printjob.id)
        assert message['time']
        assert message['text'] == 'Print Job ({}) Deleted'.format(printjob.original_filename)
        
        _job = PrintJob.query.filter_by(id=printjob.id).first()
        assert not bool(_job)


@pytest.mark.usefixtures('client_class')
class TestPrintRecord:
    
    def test_print_record(self, db):
        for i in range(100):
            PrintRecordFactory()
        db.session.commit()
        
        res = self.client.get(url_for('digital.printHistory'))
        assert res.status_code == 200
        assert b'<td>job99.zip</td>' in res.data
        assert b'<td>job50.zip</td>' in res.data
        res = self.client.get(url_for('digital.printHistory', page=2))
        assert res.status_code == 200
        assert b'<td>job49.zip</td>' in res.data
        assert b'<td>job0.zip</td>' in res.data
        res = self.client.get(url_for('digital.printHistory', page=3))
        assert res.status_code == 404
        
    def test_print_record_start_date(self, db):
        for i in range(100):
            PrintRecordFactory()
        db.session.commit()
        
        res = self.client.get(url_for('digital.printHistory', start='2018-05-10'))
        assert res.status_code == 200
        assert b'2018-05-09' not in res.data
        assert b'2018-05-10' in res.data
        
    def test_print_record_end_date(self, db):
        for i in range(100):
            PrintRecordFactory()
        db.session.commit()
        
        res = self.client.get(url_for('digital.printHistory', end='2018-05-20'))
        assert res.status_code == 200
        assert b'2018-05-21' not in res.data
        assert b'2018-05-20' in res.data
        
    def test_print_record_start_and_end_date(self, db):
        for i in range(100):
            PrintRecordFactory()
        db.session.commit()
        
        res = self.client.get(url_for('digital.printHistory', start='2018-05-10', end='2018-05-20'))
        assert res.status_code == 200
        assert b'2018-05-09' not in res.data
        assert b'2018-05-10' in res.data
        assert b'2018-05-21' not in res.data
        assert b'2018-05-20' in res.data
        


























