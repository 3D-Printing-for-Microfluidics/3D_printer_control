from datetime import datetime

from printer_server.models import PrintJob


class TestPrintJob:

    def test_get_by_id(self, app, printjob):
        retrieved = PrintJob.get_by_id(printjob.id)
        assert retrieved == printjob
