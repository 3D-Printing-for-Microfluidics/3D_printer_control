import logging

from printer_server.threading_wrapper import Thread
from printer_server.hardware_configuration import driver_handles
from printer_server.printer_control.print_control import PrintControl

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class VacuumControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.mks = driver_handles.mks
        self.mks_solenoids = driver_handles.mks_solenoids

    def connect_hardware(self):
        mks_thread = Thread(log, name="mks_connect_thread", target=self.mks.connect, args=[])
        mks_solenoids_thread = Thread(log, name="mks_solenoids_thread", target=self.mks_solenoids.connect, args=[])
        mks_thread.start()
        mks_solenoids_thread.start()
        super().connect_hardware()
        mks_thread.join()
        mks_solenoids_thread.join()

    def initialize_hardware(self):
        mks_thread = Thread(log, name="mks_init_thread", target=self.mks.initialize, args=[])
        mks_thread.start()
        super().initialize_hardware()
        mks_thread.join()