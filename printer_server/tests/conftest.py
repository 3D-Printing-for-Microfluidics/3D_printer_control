# -*- coding: utf-8 -*-
"""Defines fixtures available to all tests."""

import sys
import types

#########################################
# inject dummy modules for testing
module_name = 'printer_server.printer.solus'
dummy_module = types.ModuleType(module_name)
sys.modules[module_name] = dummy_module
_code = open('tests/dummy_files/dummy_solus.py', 'rb').read()
exec(_code, dummy_module.__dict__)

module_name = 'printer_server.printer.projector'
dummy_module = types.ModuleType(module_name)
sys.modules[module_name] = dummy_module
_code = open('tests/dummy_files/dummy_projector.py', 'rb').read()
exec(_code, dummy_module.__dict__)
#########################################

import pytest
from pytest_mock import mocker
import os
from datetime import datetime
import shutil

from printer_server.extensions import db as _db
from printer_server.app import create_app
from printer_server.settings import TestConfig
from printer_server.extensions import socketio
from printer_server.printing_threads import PrintingThreads
from printer_server.printer.print_settings import PrintSettings
from printer_server.models import PrintJob
from .factories import UserFactory, PrintJobFactory, PrintRecordFactory


@pytest.fixture
def app():
    _app = create_app(TestConfig)
    ctx = _app.test_request_context()
    ctx.push()

    yield _app

    ctx.pop()
    
    try:
        os.remove(os.path.join(TestConfig.PROJECT_ROOT, 'test.db'))
    except FileNotFoundError:
        pass


@pytest.fixture
def db(app):
    """A database for the tests."""
    _db.app = app
    with app.app_context():
        _db.create_all()

    yield _db

    # Explicitly close DB connection
    _db.session.close()
    _db.drop_all()


@pytest.fixture
def socketio_client(app):
    return socketio.test_client(app, namespace='/printing')


@pytest.fixture
def mocker_class(request, mocker):
    if request.cls is not None:
        request.cls.mocker = mocker


@pytest.fixture
def user(db):
    """A user for the tests."""
    user = UserFactory(password='myprecious')
    db.session.commit()
    return user


@pytest.fixture
def printjob(db):
    uploadTime = datetime.now()
    filename = 'correct_job.zip'
    testFile = os.path.join(TestConfig.PROJECT_ROOT, 'tests', 
                            'dummy_files', 'zipfiles', filename)
    job = PrintJob(original_filename=filename, 
                   upload_time=uploadTime, 
                   upload_ip='0.0.0.0')
    job.save()
             
    shutil.copy(testFile, os.path.join(TestConfig.UPLOAD_FOLDER, 'queue'))
    os.rename(os.path.join(TestConfig.UPLOAD_FOLDER, 'queue', filename),
              os.path.join(TestConfig.UPLOAD_FOLDER, 'queue', job.zip_filename))
    yield job
    
    try:
        os.remove(os.path.join(TestConfig.UPLOAD_FOLDER, 'queue', job.zip_filename))
        job.delete()
    except:
        pass


@pytest.fixture
def printrecord(db):
    printrecord = PrintRecordFactory()
    db.session.commit()
    return printrecord


@pytest.fixture
def pt(app, mocker):
    """Printing Thread fixture"""
    
    class DummyPrintRecord:
        def save(self):
            pass
    
    pt = PrintingThreads()
    printSettingsFile = os.path.join(TestConfig.PROJECT_ROOT, 'tests',
        'dummy_files', 'print_settings', 'print_settings.json')
    pt.printSettings = PrintSettings.fromFile(filename=printSettingsFile)
    pt.jsonDir = os.path.dirname(printSettingsFile)
    pt.printRecord=DummyPrintRecord()
    
    # Mock every projector and solus method called
    pt.projector.setLedAmplitude = mocker.MagicMock()
    pt.projector.projectMulti = mocker.MagicMock()
    pt.projector.stop = mocker.MagicMock()
    pt.projector.clear = mocker.MagicMock()
    pt.solus.homing = mocker.MagicMock()
    pt.solus.goToFirstLayerHeight = mocker.MagicMock()
    pt.solus.printCycle = mocker.MagicMock()
    pt.solus.resume = mocker.MagicMock()
    
    return pt


@pytest.fixture(scope='session')
def browser(request):
    """Source: https://www.blazemeter.com/blog/improve-your-selenium-webdriver-tests-with-pytest"""
    from selenium import webdriver
    web_driver = webdriver.Firefox()
    session = request.node
    for item in session.items:
        cls = item.getparent(pytest.Class)
        setattr(cls.obj, "browser", web_driver)
    yield
    web_driver.close()

