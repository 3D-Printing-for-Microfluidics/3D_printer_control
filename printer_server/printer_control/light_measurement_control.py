import time
import logging
from datetime import datetime

import printer_server.views.home as home
from printer_server.threading_wrapper import Thread
from printer_server.async_file_handler import async_file_hander
from printer_server.printer_control.print_control import PrintControl
from printer_server.hardware_configuration import config_dict, driver_handles

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class LightMeasurementControl(PrintControl):
    def __init__(self):
        super().__init__()
        self.spectrometer = driver_handles.spectrometer

    def connect_hardware(self):
        spectrometer_thread = Thread(log, name="spectrometer_setup_thread", target=self.spectrometer.connect, args=[])
        spectrometer_thread.start()
        super().connect_hardware()
        spectrometer_thread.join()
        if not self.spectrometer.connected:
            log.error("Spectrometer failed to connect!")
            self.all_hardware_connected = False

    def pre_print_tasks(self):
        super().pre_print_tasks()
        self.measure_light("preprint")

    def post_print_tasks(self):
        self.measure_light("postprint")
        super().post_print_tasks()

    def measure_light(self, path_prefix):
        for light_engine in config_dict["light_engines"]:
            spectra_path = str(self.current_job / f"{path_prefix}_spectra_{light_engine}.csv")

            # Move x/y/focus to spectrometer location
            x_pos = self.coord_systems[f"fiber_{light_engine}"]["X"]
            y_pos = self.coord_systems[f"fiber_{light_engine}"]["Y"]
            focus_pos = self.coord_systems[f"fiber_{light_engine}"]["Focus"]
            self.xy_threads = self.xy_stage.threadedXYMove(log, x_pos, y_pos, join=False)
            self.focus_thread = self.focus_stage.threadedFocusMove(log, focus_pos, join=False)
            for thread in self.xy_threads:
                if thread is not None:
                    thread.join()
            if self.focus_thread is not None:
                self.focus_thread.join()

            # Measure spectrum
            integration_time = config_dict["spectrometer"]["default_integration_time"]
            num_avg = config_dict["spectrometer"]["default_number_of_averages"]

            self.write_to_event_log(f"Measuring spectra for {light_engine}")
            self.spectrometer.set_integration_time(integration_time)
            spectrum = self.spectrometer.get_spectrum(num_avg)

            # Save spectrum to file
            # async_file_hander.write(spectra_path, "HEADER INFORMATION...\n")
            async_file_hander.write(spectra_path, f"Integration time: {integration_time} ms\n")
            async_file_hander.write(spectra_path, f"Number of Averages: {num_avg}\n")
            async_file_hander.write(spectra_path, "\n")
            async_file_hander.write(spectra_path, "wavelength (nm),counts\n")
            for wavelength, counts in zip(spectrum[0], spectrum[1]):
                async_file_hander.write(spectra_path, f"{wavelength},{counts}\n")