# -*- coding: utf-8 -*-
"""Test Solus."""
import pytest


class TestSolus:

    # find Solus USB port
    def test_find_solus_usb_port(self, solus):
        solus.findUsbPort()
        assert solus.port is not None

    def test_raise_valueerror_when_solus_port_is_none(self, solus):
        with pytest.raises(ValueError):
            solus.serialNum = '123456789'
            solus.connect()

    def test_solus_port_is_open(self, solus):
        solus.connect()
        assert solus.is_open is True

    def test_solus_initializing(self, solus):
        res = solsu.initialize()
        assert 'Grbl 0.9g' in res
        assert res.count('ok') == 3

    def test_planarizing(self, solus):
        res = solus.planarize()
        res += solus.goToZmax()
        assert res.count('ok') == 3

    def test_go_to_first_layer_height(self, solus):
        res = solus.goToFirstLayerHeight(0.01)
        assert res.count('ok') == 2

    def test_print_cycle(self, solus):
        res = solus.printCycle([0, 0, 0, 0, 0, 400, 400, 2, 1, 400, 400])
        assert res.count('ok') == 5