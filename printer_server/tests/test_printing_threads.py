# -*- coding: utf-8 -*-
"""Test printing threads."""
import time


# TODO: add more test for PrintingThreads
class TestPrintingThreads:
    
    def test_start_printing(self, pt, printrecord):
        pt.printer3d.state = 'planarized'
        pt.start()
        pt._thread.join()
        pt.projector.setLedAmplitude.assert_called_once_with(100)
        assert pt.projector.projectMulti.call_count == 3
        pt.projector.stop.assert_called_once()
        pt.projector.clear.assert_called_once()
        pt.solus.homing.assert_called_once()
        pt.solus.goToFirstLayerHeight.assert_called_once()
        assert pt.solus.printCycle.call_count == 2
        assert pt.printer3d.state is 'completed'
        
    def test_resume_printing_when_printer_state_is_paused(self, pt, printrecord):
        pt.printer3d.state = 'paused'
        pt.pausedLayer = 2
        pt.resume()
        pt._thread.join()
        pt.projector.setLedAmplitude.assert_called_once_with(100)
        assert pt.projector.projectMulti.call_count == 2
        pt.projector.stop.assert_called_once()
        pt.projector.clear.assert_called_once()
        pt.solus.homing.assert_called_once()
        pt.solus.resume.assert_called_once()
        assert pt.solus.printCycle.call_count == 1
        assert pt.printer3d.state is 'completed'
        
    def test_stop_printing(self, pt):
        def _wait():
            time.sleep(0.5)
        pt.solus.printCycle = _wait
        
        pt.printer3d.state = 'planarized'
        pt.start()
        pt.printingStopped.set()
        pt._thread.join()
        assert pt.projector.projectMulti.call_count < 3

    def test_pause_printing(self, pt):
        def _wait():
            time.sleep(0.5)
        pt.solus.printCycle = _wait
        
        pt.printer3d.state = 'planarized'
        pt.start()
        pt.printingPaused.set()
        pt._thread.join()
        assert pt.projector.projectMulti.call_count < 3

