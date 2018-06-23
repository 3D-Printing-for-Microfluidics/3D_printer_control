import pytest
from flask import url_for
import os
from datetime import datetime
import glob
import time
import io
import shutil

from printer_server.settings import Config
from .factories import PrintRecordFactory


def _wait(t=1):
    time.sleep(t)


@pytest.mark.usefixtures('db', 'browser')
class TestFrontEnd:
    
    def test_3d_printer_state_machine_at_front_end(self, printjob, live_server):
        live_server.start()
        
        # start with printer3d.state is None
        self.browser.get(url_for('main.index', _external=True))
        _wait()
        self.browser.find_element_by_id('init-btn').click()
        _wait()
        # The page should not redirect if popup window is dismissed
        self.browser.switch_to_alert().dismiss()
        _wait()
        
        self.browser.find_element_by_id('init-btn').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait()
        assert '<h2>Initialized</h2>' in self.browser.page_source
        
        self.browser.find_element_by_id('plana-btn').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait()
        assert '<h2>Planarizing</h2>' in self.browser.page_source
        
        self.browser.find_element_by_id('plana-btn').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait()
        assert '<h2>Planarized</h2>' in self.browser.page_source
        
        self.browser.get(url_for('main.index', _external=True))
        _wait()
        self.browser.execute_script('document.getElementById("row-1").click()')
        _wait()
        self.browser.find_element_by_id('start-btn').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait()
        assert '<h2>Printing</h2>' in self.browser.page_source
        
        self.browser.find_element_by_id('pause-btn').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait(3)
        assert '<h2>Paused</h2>' in self.browser.page_source
        
        self.browser.find_element_by_id('resume-btn').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait()
        assert '<h2>Printing</h2>' in self.browser.page_source
        
        _wait(3)
        self.browser.get(url_for('main.index', _external=True))
        _wait()
        assert '<h2>Completed</h2>' in self.browser.page_source
        
        for f in glob.glob(os.path.join(Config.UPLOAD_FOLDER, '**/job*.zip'), 
                           recursive=True):
            os.remove(f)
        shutil.rmtree(os.path.join(Config.UPLOAD_FOLDER, 'current_job'))
        
    def test_stop_during_printing(self, printjob, live_server):
        live_server.app.printer3d.state = 'planarized'
        live_server.start()
        
        self.browser.get(url_for('main.index', _external=True))
        _wait()
        self.browser.execute_script('document.getElementById("row-1").click()')
        _wait()
        self.browser.find_element_by_id('start-btn').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait()
        assert '<h2>Printing</h2>' in self.browser.page_source
        
        self.browser.find_element_by_id('stop-btn').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait(3)
        assert '<h2>Stopped</h2>' in self.browser.page_source
        
        for f in glob.glob(os.path.join(Config.UPLOAD_FOLDER, '**/job*.zip'), 
                           recursive=True):
            os.remove(f)
        shutil.rmtree(os.path.join(Config.UPLOAD_FOLDER, 'current_job'))
        
    def test_stop_after_pausing_printing(self, printjob, live_server):
        live_server.app.printer3d.state = 'planarized'
        live_server.start()
        
        self.browser.get(url_for('main.index', _external=True))
        _wait()
        self.browser.execute_script('document.getElementById("row-1").click()')
        _wait()
        self.browser.find_element_by_id('start-btn').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait()
        assert '<h2>Printing</h2>' in self.browser.page_source
        
        self.browser.find_element_by_id('pause-btn').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait(3)
        assert '<h2>Paused</h2>' in self.browser.page_source
        
        self.browser.find_element_by_id('stop-btn').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait(3)
        assert '<h2>Stopped</h2>' in self.browser.page_source
        
        for f in glob.glob(os.path.join(Config.UPLOAD_FOLDER, '**/job*.zip'), 
                           recursive=True):
            os.remove(f)
        shutil.rmtree(os.path.join(Config.UPLOAD_FOLDER, 'current_job'))


@pytest.mark.usefixtures('db')
class TestDeletingPrintJob:
    
    def test_delete_print_job_at_create_job_page(self, printjob, live_server):
        live_server.start()
        self.browser.get(url_for('digital.jobs', _external=True))
        _wait()
        self.browser.find_element_by_id('delete-job1').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait()
        assert '<td>current_job.zip</td>' not in self.browser.page_source
        
    def test_delete_print_job_at_planarized_page(self, printjob, live_server):
        live_server.app.printer3d.state = 'planarized'
        live_server.start()
        self.browser.get(url_for('main.index', _external=True))
        _wait()
        self.browser.find_element_by_id('delete-job1').click()
        _wait()
        self.browser.switch_to_alert().accept()
        _wait()
        assert '<td>current_job.zip</td>' not in self.browser.page_source


@pytest.mark.usefixtures('browser')
class TestPrintRecord:
    
    def test_print_record(self, db, live_server):
        for i in range(100):
            PrintRecordFactory()
        db.session.commit()
        
        live_server.start()
        self.browser.get(url_for('digital.printHistory', _external=True))
        _wait()
        assert '<td>job99.zip</td>' in self.browser.page_source
        assert '<td>job50.zip</td>' in self.browser.page_source
        self.browser.get(url_for('digital.printHistory', page=2, _external=True))
        _wait()
        assert '<td>job49.zip</td>' in self.browser.page_source
        assert '<td>job0.zip</td>' in self.browser.page_source
        
    def test_print_record_pagination_with_start_and_end_date(self, db, live_server):
        for i in range(100):
            PrintRecordFactory()
        db.session.commit()
        
        live_server.start()
        self.browser.get(url_for('digital.printHistory', _external=True))
        _wait()
        self.browser.find_element_by_id('datepicker-from').send_keys('2018-05-05')
        self.browser.find_element_by_id('datepicker-to').send_keys('2018-05-25')
        _wait()
        self.browser.find_element_by_id('submit').click()
        _wait()
        self.browser.find_elements_by_class_name('page-link')[-1].click()
        _wait()
        assert '2018-05-04' not in self.browser.page_source
        assert '2018-05-26' not in self.browser.page_source

















