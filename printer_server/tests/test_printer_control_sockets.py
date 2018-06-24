# -*- coding: utf-8 -*-
"""Test printer control sockets."""
import pytest
import os
import io
import shutil
from flask import url_for
from datetime import datetime
import time

from printer_server.settings import Config
from printer_server.models import PrintJob, PrintRecord
from printer_server.threads import printingThreads as pt
from printer_server.printer.print_settings import PrintSettings


def _wait(t=0.05):
    time.sleep(t)


@pytest.mark.usefixtures('mocker_class')
class TestInit:

    def test_connect_and_initialize_when_printer_state_is_wrong(self, app, socketio_client):
        received = socketio_client.get_received(namespace='/printing')
        assert received[0]['name'] == 'uninitialized'
        pt.initialize = self.mocker.MagicMock()
        app.printer3d.state = 'wrong state'
        socketio_client.emit('initialize', dict(), namespace='/printing')
        pt.initialize.assert_not_called()
        
    def test_connect_and_initialize_when_printer_state_is_uninitialized(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.initialize = self.mocker.MagicMock()
        app.printer3d.state = 'uninitialized'
        socketio_client.emit('initialize', dict(), namespace='/printing')
        pt.initialize.assert_called_once()


@pytest.mark.usefixtures('client_class', 'mocker_class')
class TestPlanarizationStep1:
    
    def test_planarization_step1_when_printer_state_is_wrong(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.planarizationStep1 = self.mocker.MagicMock()
        app.printer3d.state = 'wrong state'
        socketio_client.emit('planarization step 1', dict(), namespace='/printing')
        pt.planarizationStep1.assert_not_called()
        
    def test_planarization_step1_when_printer_state_is_initialized(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.planarizationStep1 = self.mocker.MagicMock()
        app.printer3d.state = 'initialized'
        socketio_client.emit('planarization step 1', dict(), namespace='/printing')
        pt.planarizationStep1.assert_called_once()
        
    def test_planarization_step1_when_printer_state_is_planarized(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.planarizationStep1 = self.mocker.MagicMock()
        app.printer3d.state = 'planarized'
        socketio_client.emit('planarization step 1', dict(), namespace='/printing')
        pt.planarizationStep1.assert_called_once()
        
    def test_planarization_step1_when_printer_state_is_completed(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.planarizationStep1 = self.mocker.MagicMock()
        app.printer3d.state = 'completed'
        socketio_client.emit('planarization step 1', dict(), namespace='/printing')
        pt.planarizationStep1.assert_called_once()
        
    def test_planarization_step1_when_printer_state_is_stopped(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.planarizationStep1 = self.mocker.MagicMock()
        app.printer3d.state = 'stopped'
        socketio_client.emit('planarization step 1', dict(), namespace='/printing')
        pt.planarizationStep1.assert_called_once()


@pytest.mark.usefixtures('mocker_class')
class TestPlanarizationStep2:
    
    def test_planarization_step2_when_printer_state_is_wrong(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.planarizationStep2 = self.mocker.MagicMock()
        app.printer3d.state = 'wrong state'
        socketio_client.emit('planarization step 2', dict(), namespace='/printing')
        pt.planarizationStep2.assert_not_called()
        
    def test_planarization_step2_when_printer_state_is_planarizing(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.planarizationStep2 = self.mocker.MagicMock()
        app.printer3d.state = 'planarizing'
        socketio_client.emit('planarization step 2', dict(), namespace='/printing')
        pt.planarizationStep2.assert_called_once()


@pytest.mark.usefixtures('mocker_class')
class TestStart:
    
    def test_start_when_printer_state_is_wrong(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.start = self.mocker.MagicMock()
        app.printer3d.state = 'wrong state'
        socketio_client.emit('start', dict(), namespace='/printing')
        pt.start.assert_not_called()
        
    def test_start_when_printer_state_is_planarized_but_no_job_is_selected(self, app, socketio_client, db):
        socketio_client.get_received(namespace='/printing')
        pt.start = self.mocker.MagicMock()
        app.printer3d.state = 'planarized'
        socketio_client.emit('start', {'job': None}, namespace='/printing')
        pt.start.assert_not_called()
        
    def test_start_when_printer_state_is_planarized_but_job_doesnt_exist(self, app, socketio_client, db):
        socketio_client.get_received(namespace='/printing')
        pt.start = self.mocker.MagicMock()
        app.printer3d.state = 'planarized'
        socketio_client.emit('start', {'job': 1}, namespace='/printing')
        assert app.printer3d.state is 'planarized'
        pt.start.assert_not_called()
        
    def test_start_when_printer_state_is_planarized_and_job_exists(self, app, client, socketio_client, db):
        # Mock every projector and solus method called
        pt.start = self.mocker.MagicMock()
        
        def __wait():
            time.sleep(0.5)
        pt.solus.homing = __wait
        
        # Upload a file for testing
        filename = 'correct_job.zip'
        testFile = os.path.join(Config.PROJECT_ROOT, 'tests',
                                'dummy_files', 'zipfiles', filename)
        content = open(testFile, 'rb').read()
        res = client.post(url_for('digital.handleUpload'),
            data=dict(file=(io.BytesIO(content), filename)))
        assert res.status_code == 200

        job = PrintJob.query.filter_by(original_filename=filename).first()
        app.printer3d.state = 'planarized'
        socketio_client.emit('start', {'job': job.id}, namespace='/printing')
        assert os.path.exists(os.path.join(Config.UPLOAD_FOLDER, 'print_history', job.zip_filename))
        assert os.path.exists(os.path.join(Config.UPLOAD_FOLDER, 'current_job'))
        # assert the started job is deleted from queue
        assert not PrintJob.get_by_id(job.id)
        assert res.status_code == 200
        pt.start.assert_called_once()
        shutil.rmtree(os.path.join(Config.UPLOAD_FOLDER, 'current_job'))
        os.remove(os.path.join(Config.UPLOAD_FOLDER, 'print_history', job.zip_filename))


@pytest.mark.usefixtures('mocker_class')
class TestPause:
    
    def test_pause_when_printer_state_is_wrong(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.pause = self.mocker.MagicMock()
        app.printer3d.state = 'wrong state'
        socketio_client.emit('pause', dict(), namespace='/printing')
        pt.pause.assert_not_called()
        
    def test_pause_when_printer_state_is_printing(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.pause = self.mocker.MagicMock()
        app.printer3d.state = 'printing'
        socketio_client.emit('pause', dict(), namespace='/printing')
        pt.pause.assert_called_once()


@pytest.mark.usefixtures('mocker_class')
class TestResume:
    
    def test_resume_when_printer_state_is_wrong(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.resume = self.mocker.MagicMock()
        app.printer3d.state = 'wrong state'
        socketio_client.emit('resume', dict(), namespace='/printing')
        pt.resume.assert_not_called()
        
    def test_resume_when_printer_state_is_paused(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.resume = self.mocker.MagicMock()
        app.printer3d.state = 'paused'
        socketio_client.emit('resume', dict(), namespace='/printing')
        pt.resume.assert_called_once()


@pytest.mark.usefixtures('mocker_class')
class TestStop:
    
    def test_stop_when_printer_state_is_wrong(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.stop = self.mocker.MagicMock()
        app.printer3d.state = 'wrong state'
        socketio_client.emit('stop', dict(), namespace='/printing')
        pt.stop.assert_not_called()
        
    def test_stop_when_printer_state_is_printing(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.stop = self.mocker.MagicMock()
        app.printer3d.state = 'printing'
        socketio_client.emit('stop', dict(), namespace='/printing')
        pt.stop.assert_called_once()
        
    def test_stop_when_printer_state_is_paused(self, app, socketio_client):
        socketio_client.get_received(namespace='/printing')
        pt.stop = self.mocker.MagicMock()
        app.printer3d.state = 'paused'
        socketio_client.emit('stop', dict(), namespace='/printing')
        pt.stop.assert_called_once()

