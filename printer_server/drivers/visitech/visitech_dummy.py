"""
Dummy Visitech Module
=====================
"""
import time
import logging
from datetime import datetime
from printer_server.drivers.screen import screen
from printer_server.logging_handler import dummy_log
from printer_server.drivers.generic_drivers import LightEngineDriver

class Visitech_dummy(LightEngineDriver):
    """
    Dummy Visitech class for testing and development.
    """
    def __init__(
        self,
        leds=None,
        config_dict=None,
        log_level=logging.DEBUG,
        dual_led=False,
        screen=None,
    ):
        self.max_exp_time = 10000
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.config_dict = config_dict or {}
        if self.config_dict:
            leds = self.config_dict.get("leds_nm", leds)
            dual_led = self.config_dict.get("dual_led", dual_led)
        self.host = self.config_dict.get("address", "192.168.0.10")
        self.port = self.config_dict.get("port", 5000)
        self.socket = None
        self.connected = False
        self.exposure_time = 0
        self.led_on = False
        self.repeats = 1
        self.led = 0
        self.led_power = 0
        self.normalization_factor = 1.0
        self.is_idle = False
        self.dual_led = dual_led
        self.leds = leds or []
        self.suppress_ocp_error = False
        self.hdmi_reset = False
        self.hdmi_output = self.config_dict.get("hdmi_output", 1)
        self.hdmi_reset_script = self.config_dict.get(
            "hdmi_reset_script",
            "/home/pi/3D_printer_control/rpi/reset_hdmi.sh",
        )
        self.screen = screen

    @dummy_log
    def connect(self):
        self.connected = True
        return True

    @dummy_log
    def initialize(self):
        pass

    @dummy_log
    def disconnect(self):
        self.connected = False

    # @dummy_log
    def send(self, msg, data=None):
        self.log.debug("Sent:  '%s'", msg)
        return "+OK"

    # @dummy_log
    def load_defaults(self):
        return self.send("LOAD DEFAULTS")

    # @dummy_log
    def set_static_ip(self, address):
        return self.send(f"SET STATIC IP ADDR {address}")

    # @dummy_log
    def get_version(self):
        return self.send("GET VERSION")

    # @dummy_log
    def led_driver_enable(self, led_num=0):
        return self.send(f"SET LIGHT ON {led_num}")

    # @dummy_log
    def led_driver_disable(self, led_num=0):
        return self.send(f"SET LIGHT OFF {led_num}")

    # @dummy_log
    def get_led_driver_status(self, led_num=0):
        return self.send(f"GET LIGHT STATUS {led_num}")

    # @dummy_log
    def get_led_state(self, led_num=0):
        return self.send(f"GET LIGHT OUTPUT STATUS {led_num}")

    # @dummy_log
    def set_led_amplitude(self, amplitude, led_num=0):
        return self.send(f"SET AMPLITUDE {led_num} {amplitude}")

    # @dummy_log
    def get_led_amplitude(self, led_num=0):
        return self.send(f"GET AMPLITUDE {led_num}")

    # @dummy_log
    def set_led_driver_ocp(self, value, led_num=0):
        return self.send(f"SET OCP {led_num} {value}")

    # @dummy_log
    def get_led_driver_ocp(self, led_num=0):
        return self.send(f"GET OCP {led_num}")

    # @dummy_log
    def set_led_driver_regulation_mode(self, mode, led_num=0):
        return self.send(f"SET REG MODE {led_num} {mode}")

    # @dummy_log
    def get_led_driver_regulation_mode(self, led_num=0):
        return self.send(f"GET REG MODE {led_num}")

    # @dummy_log
    def get_led_driver_current(self, led_num=0):
        return self.send(f"GET CURRENT FEEDBACK {led_num}")

    # @dummy_log
    def get_led_intensity(self, led_num=0):
        return self.send(f"GET LIGHT FEEDBACK {led_num}")

    # @dummy_log
    def get_led_temp(self, led_num=0):
        return self.send(f"GET LED TEMP {led_num}")

    # @dummy_log
    def get_led_driver_board_temp(self, led_num=0):
        return self.send(f"GET BOARD TEMP {led_num}")

    # @dummy_log
    def set_led_driver_board_temp_limit(self, temperature, led_num=0):
        return self.send(f"SET BOARD TEMP LIMIT {led_num} {temperature}")

    # @dummy_log
    def get_led_driver_board_temp_limit(self, led_num=0):
        return self.send(f"GET BOARD TEMP LIMIT {led_num}")

    # @dummy_log
    def set_led_temp_limit(self, temperature, led_num=0):
        return self.send(f"SET LED TEMP LIMIT {led_num} {temperature}")

    # @dummy_log
    def get_led_temp_limit(self, led_num=0):
        return self.send(f"GET LED TEMP LIMIT {led_num}")

    # @dummy_log
    def start_sequencer(self):
        return self.send("SET SEQ ON")

    @dummy_log
    def stop_sequencer(self):
        self.led_on = False
        return self.send("SET SEQ OFF")

    # @dummy_log
    def pause_sequencer(self):
        return self.send("SET SEQ PAUSE")

    # @dummy_log
    def get_dmd_status(self):
        return self.send("GET DMD STATUS")

    # @dummy_log
    def set_dmd_operation_mode(self, mode):
        return self.send(f"SET OPERATION MODE {mode}")

    # @dummy_log
    def get_dmd_operation_mode(self):
        return self.send("GET OPERATION MODE")

    # @dummy_log
    def set_sequencer_lut_definition(self, exposure, darktime=0, clear=1, bitdepth=8, wait_for_trigger=1, pattern_index=0, bit_index=0):
        return self.send(f"SET LUT DEFINITION\r\n{exposure},{darktime},{clear},{bitdepth},{wait_for_trigger},{pattern_index},{bit_index}")

    # @dummy_log
    def set_sequencer_lut_config(self, num_sequences=1, repeats=1):
        return self.send(f"SET LUT CONFIG {num_sequences} {repeats}")

    # @dummy_log
    def upload_image(self, filename, pattern_index):
        return self.send(f"UPLOAD IMAGE PATTERN\r\n{pattern_index}\r\n{filename}")

    # @dummy_log
    def set_video_source(self, source="HDMI"):
        return self.send(f"INIT {source}")

    # @dummy_log
    def get_video_source(self):
        return self.send("GET INPUT SOURCE")

    # @dummy_log
    def set_pixel_mode(self, mode):
        return self.send(f"SET PIXEL MODE {mode}")

    # @dummy_log
    def park_dmd_mirrors(self):
        return self.send("SET MIRRORS PARKED")

    # @dummy_log
    def unpark_dmd_mirrors(self):
        return self.send("SET MIRRORS UNPARKED")

    def idle_on(self):
        if not self.is_idle:
            self.is_idle = True
            self.log.info("DMD idle on")
        return self.send("SET MIRROR SHAKE ON")

    def idle_off(self):
        if self.is_idle:
            self.is_idle = False
            self.log.info("DMD idle off")
        return self.send("SET MIRROR SHAKE OFF")

    # @dummy_log
    def get_sticky_errors(self, warn="ALL"):
        return self.send("GET STICKY ERRORS")

    # @dummy_log
    def get_logs(self):
        return self.send("GET LOGS")

    # @dummy_log
    def get_normalization_factor(self):
        return float(self.send("FACTORY GET NORMALIZATION VALUE"))

    # @dummy_log
    def set_normalization_factor(self, normalization_factor):
        self.normalization_factor = normalization_factor
        return self.send(f"FACTORY SET NORMALIZATION VALUE {normalization_factor}")

    # @dummy_log
    def split_exposure_time(self, exposure):
        n = int(exposure // self.max_exp_time)
        if exposure % self.max_exp_time != 0:
            exposure = [self.max_exp_time] * n + [exposure % self.max_exp_time]
        else:
            exposure = [self.max_exp_time] * n
        return exposure

    # @dummy_log
    def read_all_status(self, warn="ALL"):
        status = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "led_feedback": self.get_led_intensity(),
            "led_temp": self.get_led_temp(),
            "led_driver_temp": self.get_led_driver_board_temp(),
            "led_sticky_errors": self.get_sticky_errors(warn),
            "led_driver_status": self.get_led_driver_status(),
            "led_feedback2": "",
            "led_temp2": "",
            "led_driver_temp2": "",
            "led_driver_status2": "",
        }
        if self.dual_led:
            status["led_feedback2"] = self.get_led_intensity(led_num=1)
            status["led_temp2"] = self.get_led_temp(led_num=1)
            status["led_driver_temp2"] = self.get_led_driver_board_temp(led_num=1)
            status["led_driver_status2"] = self.get_led_driver_status(led_num=1)
        return status
    
    @dummy_log
    def set_image(self, img_path, led_num=0, grayscale_corrected=False, mirror_short=False, mirror_long=False, _grayscale_correction_path=None):
        """
        Sets the image to be drawn
        """
        self.screen.setCorrectionEnable(grayscale_corrected, light_engine="visitech")
        self.screen.draw(img_path, light_engine="visitech", led_num=led_num, mirror_short=mirror_short, mirror_long=mirror_long, _grayscale_correction_path=_grayscale_correction_path)

    def get_image(self):
        """
        Gets the current image from the screen
        """
        return self.screen.get_image("visitech")

    @dummy_log
    def get_image_preview(self, scale=1/20):
        """
        Get a preview of the current image.
        """
        return self.screen.fetch_preview("visitech", scale=scale)
    
    def is_grayscale_corrected(self):
        return self.screen.getCorrectionEnable("visitech")

    def getCurrentLed(self):
        return self.led

    @dummy_log
    def setup_exposure(self, exposure_time_ms, led_power=100, repeat=1, led_num=0):
        self.exposure_time = exposure_time_ms
        self.repeats = repeat
        self.led = led_num
        self.led_power = led_power

        if self.is_grayscale_corrected():
            self.normalization_factor = self.config_dict.get(
                "grayscale_normalization_factor",
                [1.0],
            )[led_num]
        else:
            self.normalization_factor = self.config_dict.get(
                "normalization_factor",
                [1.0],
            )[led_num]

        # if self.is_grayscale_corrected():
        #     self.set_normalization_factor(self.config_dict["grayscale_normalization_factor"][led_num])
        # else:
        #     self.set_normalization_factor(self.config_dict["normalization_factor"][led_num])

        if self.dual_led:
            if led_num == 0:
                self.led_driver_enable(led_num=0)
                self.led_driver_disable(led_num=1)
            else:
                self.led_driver_enable(led_num=1)
                self.led_driver_disable(led_num=0)

        min_t = 4.046
        max_t = 10000
        self.log.debug(
            "Setting up exposure at %s for %s ms at power setting %s. Repeat %s",
            self.leds[led_num],
            exposure_time_ms,
            led_power,
            repeat,
        )
        if exposure_time_ms == 0:
            return
        elif exposure_time_ms > max_t:
            msg = f"Exposure time {exposure_time_ms} ms is greater than maximum possible exposure time "
            msg += f"of {max_t} ms. Using exposure time of {max_t} ms instead."
            self.log.warning(msg)
            exposure_time_ms = max_t
            self.exposure_time = max_t
        elif exposure_time_ms < min_t:
            msg = f"Exposure time {exposure_time_ms} ms is less than minimum possible exposure time "
            msg += f"of {min_t} ms. Using exposure time of {min_t} ms instead."
            self.log.warning(msg)
            exposure_time_ms = min_t
            self.exposure_time = min_t
        self.set_led_amplitude(led_power, led_num=led_num)
        self.set_sequencer_lut_definition(exposure=int(exposure_time_ms * 1000))
        self.set_sequencer_lut_config(repeats=repeat)

    @dummy_log
    def perform_exposure(self):
        self.led_on = True
        if self.repeats == 0:
            self.log.info(
                "Exposing %s at a power of %s indefinatly",
                self.led,
                self.led_power
            )
            self.start_sequencer()
        else:
            if self.exposure_time != 0:
                self.log.info(
                    "Exposing %s for %s ms at a power of %s",
                    self.led,
                    self.exposure_time,
                    self.led_power
                )
                self.start_sequencer()
                time.sleep(self.exposure_time * 1e-3)
            self.led_on = False

    @dummy_log
    def project(self, exposure, power, repeats=1, led_num=0):
        self.led = led_num
        self.led_power = power
        self.repeats = repeats
        if self.dual_led:
            if led_num == 0:
                self.led_driver_enable(led_num=0)
                self.led_driver_disable(led_num=1)
            else:
                self.led_driver_enable(led_num=1)
                self.led_driver_disable(led_num=0)

        self.set_led_amplitude(power, led_num=led_num)
        self.led_on = True
        if repeats == 0:  # if continuous display is desired
            self.log.info(
                "Exposing %s at a power of %s indefinatly",
                self.leds[led_num],
                power
            )
            # this provides the minimum blanking of 233 us of the full 33333 us cycle
            # (at 30Hz on HDMI)
            self.set_sequencer_lut_definition(33100, 0, 0, 8, 0, 0, 0)
            self.set_sequencer_lut_config(repeats=0)
            self.start_sequencer()  # sequencer will be stopped on program exit
        else:  # normal display is desired
            self.log.info(
                "Exposing %s for %s ms at a power of %s",
                self.leds[led_num],
                exposure,
                power
            )
            for t in self.split_exposure_time(exposure):
                # the TI board expects exposure in microseconds
                self.set_sequencer_lut_definition(exposure=int(t * 1000))
                self.set_sequencer_lut_config(repeats=repeats)
                self.start_sequencer()
                time.sleep(t * 1e-3)
                self.led_on = False

    def get_led_status(self):
        return self.led_on