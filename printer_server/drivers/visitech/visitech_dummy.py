import time

from printer_server.logging_handler import dummy_log

# pylint:disable=too-many-public-methods
class Visitech_dummy:
    @dummy_log
    def __init__(self):
        self.max_exp_time = 10000  # max single projection time in ms
        self.led_on = False

    @dummy_log
    def connect(self):
        pass

    @dummy_log
    def disconnect(self):
        pass

    @dummy_log
    def send(self, data):
        return f"sent {data}"

    def load_defaults(self):
        return self.send("LOAD DEFAULTS")

    def set_static_ip(self, address):
        return self.send("SET STATIC IP ADDR {}".format(address))

    def get_version(self):
        return self.send("GET VERSION")

    def led_driver_enable(self):
        return self.send("SET LIGHT ON")

    def led_driver_disable(self):
        return self.send("SET LIGHT OFF")

    def get_led_driver_status(self):
        return self.send("GET LIGHT STATUS")

    def get_led_state(self):
        return self.send("GET LIGHT OUTPUT STATUS")

    def set_led_amplitude(self, amplitude):
        return self.send("SET AMPLITUDE {}".format(amplitude))

    def get_led_amplitude(self):
        return self.send("GET AMPLITUDE")

    def set_led_driver_ocp(self, value):
        return self.send("SET OCP {}".format(value))

    def get_led_driver_ocp(self):
        return self.send("GET OCP")

    def set_led_driver_regulation_mode(self, mode):
        return self.send("SET REG MODE {}".format(mode))

    def get_led_driver_regulation_mode(self):
        return self.send("GET REG MODE")

    def get_led_driver_current(self):
        return self.send("GET CURRENT FEEDBACK")

    def get_led_intensity(self):
        return self.send("GET LIGHT FEEDBACK")

    def get_led_temp(self):
        return self.send("GET LED TEMP")

    def get_led_driver_board_temp(self):
        return self.send("GET BOARD TEMP")

    def set_led_driver_board_temp_limit(self, temperature):
        return self.send("SET BOARD TEMP LIMIT {}".format(temperature))

    def get_led_driver_board_temp_limit(self):
        return self.send("GET BOARD TEMP LIMIT")

    def set_led_temp_limit(self, temperature):
        return self.send("SET LED TEMP LIMIT {}".format(temperature))

    def get_led_temp_limit(self):
        return self.send("GET LED TEMP LIMIT")

    def start_sequencer(self):
        return self.send("SET SEQ ON")

    def stop_sequencer(self):
        self.led_on = False
        return self.send("SET SEQ OFF")

    def pause_sequencer(self):
        return self.send("SET SEQ PAUSE")

    def get_dmd_status(self):
        return self.send("GET DMD STATUS")

    def set_dmd_operation_mode(self, mode):
        return self.send("SET OPERATION MODE {}".format(mode))

    def get_dmd_operation_mode(self):
        return self.send("GET OPERATION MODE")

    # pylint: disable=too-many-arguments
    def set_sequencer_lut_definition(
        self,
        exposure,
        darktime=0,
        clear=1,
        bitdepth=8,
        wait_for_trigger=1,
        pattern_index=0,
        bit_index=0,
    ):
        return self.send(
            "SET LUT DEFINITION\r\n{},{},{},{},{},{},{}".format(
                exposure,
                darktime,
                clear,
                bitdepth,
                wait_for_trigger,
                pattern_index,
                bit_index,
            )
        )

    def set_sequencer_lut_config(self, num_sequences=1, repeats=1):
        return self.send("SET LUT CONFIG {} {}".format(num_sequences, repeats))

    def upload_image(self, pattern_index, bitmap_size, bitmap_data):
        return self.send(
            "UPLOAD IMAGE PATTERN\r\n{}\r\n{}\r\n{}".format(
                pattern_index, bitmap_size, bitmap_data
            )
        )

    def set_video_source(self, source="HDMI"):
        if source == "DISPLAYPORT":
            return self.send("INIT DISPLAYPORT")
        return self.send("INIT HDMI")

    def get_video_source(self):
        return self.send("GET INPUT SOURCE")

    def set_pixel_mode(self, mode):
        return self.send("SET PIXEL MODE {}".format(mode))

    def park_dmd_mirrors(self):
        return self.send("SET MIRRORS PARKED")

    def unpark_dmd_mirrors(self):
        return self.send("SET MIRRORS UNPARKED")

    def get_sticky_errors(self, warn="ALL"):
        self.send("GET STICKY ERRORS")
        return ""

    def get_logs(self):
        return self.send("GET LOGS")

    def get_normalization_factor(self):
        return float(self.send("FACTORY GET NORMALIZATION VALUE"))

    def set_normalization_factor(self, normalization_factor):
        return self.send(f"FACTORY SET NORMALIZATION VALUE {normalization_factor}")

    def split_exposure_time(self, exposure):
        """
        Split a long exposure time into an array of smaller exposure times.
        """
        n = int(exposure // self.max_exp_time)
        if exposure % self.max_exp_time != 0:
            exposure = [self.max_exp_time] * n + [exposure % self.max_exp_time]
        else:
            exposure = [self.max_exp_time] * n
        return exposure

    def read_all_status(self, warn="ALL"):
        return {
            "dmd_status": self.get_dmd_status(),
            "led_feedback": self.get_led_intensity(),
            "led_temp": self.get_led_temp(),
            "led_driver_temp": self.get_led_driver_board_temp(),
            "led_sticky_errors": self.get_sticky_errors(warn),
            "led_driver_status": self.get_led_driver_status(),
        }

    @dummy_log
    def setup_exposure(self, t, p, r=1):
        """
        Setup an exposure.
            t - exposure time in milliseconds
            p - power setting
            r - number of repeats
        """
        self.exposure_time = t
        min_t = 4.046
        max_t = 10000
        if t > max_t:
            t = max_t
            self.exposure_time = max_t
        elif t < min_t:
            t = min_t
            self.exposure_time = min_t
        self.set_led_amplitude(p)
        self.set_sequencer_lut_definition(exposure=t * 1000)
        self.set_sequencer_lut_config(repeats=r)

    @dummy_log
    def perform_exposure(self):
        """
        Start an exposure.
        """
        self.led_on = True
        if self.exposure_time != 0:
            self.start_sequencer()
            time.sleep(self.exposure_time * 1e-3)
        self.led_on = False

    @dummy_log
    def project(self, exposure, power, repeats=1):
        """
        Call all of the necessary methods to project an image, and block
        until projection is complete.
        """
        self.set_led_amplitude(power)
        self.led_on = True
        if repeats == 0:  # if continuous display is desired
            # this provides the minimum blanking of 233 us of the full 33333 us cycle
            # (at 30Hz on HDMI)
            self.set_sequencer_lut_definition(33100, 0, 0, 8, 0, 0, 0)
            self.set_sequencer_lut_config(repeats=0)
            self.start_sequencer()  # sequencer will be stopped on program exit
        else:  # normal display is desired
            for t in self.split_exposure_time(exposure):
                # the TI board expects exposure in microseconds
                self.set_sequencer_lut_definition(exposure=t * 1000)
                self.set_sequencer_lut_config(repeats=repeats)
                self.start_sequencer()
                time.sleep(t * 1e-3)
                self.led_on = False
