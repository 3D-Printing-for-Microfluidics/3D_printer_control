"""
Visitech
=========
"""
import sys
import time
import json
import atexit
import socket
import logging
from datetime import datetime

from printer_server.drivers.generic_drivers import LightEngineDriver

# pylint:disable=too-many-public-methods
class Visitech(LightEngineDriver):
    """
    This driver is based on the Visitech Ethernet interface and API.
    Commands are sent over a TCP connection.

    Here is a list of possible errors for different commands:

    - NOT_CONNECTED -1 Lost connection with onboard DLP controller or
       LED driver.
    - OUT_OF_MEMORY -2 Onboard computer out of memory.
    - OPEN_DEVICE_FAILED -3 Could not open device for writing.
    - I2C_SEND_FAILED -4 I2C communication with onboard controller
       failed.
    - I2C_READ_FAILED -5 I2C communication with onboard controller
       failed.
    - I2C_DEVICE_LIST_FAILED -6 Could not enumerate I2C devices on bus.
    - I2C_DEVICE_LIST_EMPTY -7 I2C device list is empty.
    - I2C_READ_SHORT -8 I2C communication corrupt, read were too short.
    - I2C_WRITE_SHORT -9 I2C communication corrupt, write were too
       short.
    - I2C_MASTER_SET_FAIL -10 I2C communication issue, could not set
       self as bus master.
    - TO_HIGH_LED_AMPLITUDE -11 LED amplitude value too high to set.
       0-2000 is acceptable range.
    - SEQUENCE_FILE_ERROR -12 Sequence file is not valid.
    - SEQUENCE_NUM_ARGS -13 Sequence file has too many arguments.
    - SEQUENCE_TOO_MANY_PATTERNS -14 Sequence file has too many
       patterns.
    - STRESS_TEST_FAILED -15 Stress test has failed.
    - ARGUMENT_INVALID -16 Argument is invalid.
    - ARGUMENT_OUT_OF_RANGE -17 Argument is out of range.
    - TEST_FAILED -19 Self test has failed.
    - DEVICE_COMMUNICATION_FAILED -20 Internal communication error.
    - OPEN_FILE_FAILED -21 Could not open internal file. SD card may be
       corrupt.
    - INVALID_ARGUMENT -1000 Invalid serialization protocol argument
       sent.
    - INVALID_COMMAND -1001 Invalid serialization protocol command sent.
    - RUNTIME_ERROR -1002 Unknown runtime error. See message.
    - I2C_BUS_DOWN -1003 Onboard CPU is not connected to any devices.

    These error codes will also appear when using GET LOGS if any are
    available.

    There are two commands not documented in the API but are present on
    the device that I have implemented. See the appropriate docstring
    for details:

    GET LED TEMP
    GET BOARD TEMP

    There are several other commands present in Visitech's firmware that
    aren't documented in their API that I have not implemented because
    we don't need them/I am not sure what they do. Don't implement them
    unless we figure out what they do:

    PING
    GET LBREG
    SET LBREG
    """

    def __init__(self, leds, log_level=logging.DEBUG, dual_led=False):
        self.max_exp_time = 10000  # max single projection time in ms
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        # setup TCP connection
        self.host = "192.168.0.10"
        self.port = 5000
        self.socket = (
            None  # start as None so we can tell if a connection has been attempted
        )

        self.connected = False
        self.exposure_time = 0
        self.led_on = False
        self.dual_led = dual_led
        self.leds = leds
        self.suppress_ocp_error = False

    def connect(self, shutdown):
        attempts=10
        timeout=1
        self.log.info("Connecting to light engine, this may take up to 1 minute...")

        # start TCP connection
        i = 0
        self.connected = False
        while i < attempts:  # try up to attempts number of times to create a connection
            i += 1
            try:  # attempt a new connection
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(10)
                self.socket.connect((self.host, self.port))
                self.connected = True
                self.shutdown = shutdown
            except (OSError, socket.timeout) as e:
                self.log.info("%s. Retrying in %s second(s)", e, timeout)
                self.socket = None  # get rid of handle to bad socket
                time.sleep(timeout)  # wait to try again
        if not self.connected:  # connection failed every time, notify user
            msg = "Visitech light engine not found!"
            self.log.critical(msg)
            return False

        # register exit handlers
        atexit.register(self.disconnect)
        self.log.info("Connected to Visitech light engine")
        return True

    def initalize(self):
        # set default state for light engine and clear previous errors
        self.get_sticky_errors(warn="NONE")
        self.set_video_source("HDMI")
        if self.dual_led:
            self.set_led_driver_regulation_mode("LIGHT", led_num=0)
            self.set_led_driver_regulation_mode("LIGHT", led_num=1)
        else:
            self.set_led_driver_regulation_mode("LIGHT")
        self.set_dmd_operation_mode("VIDEO_PATTERN_MODE")
        self.log.info("Visitech light engine initialized")

    def disconnect(self):
        if self.connected and self.socket is not None:
            try:
                self.stop_sequencer()  # make sure DMD is stopped on exit
                self.socket.close() # close the TCP conenction on exit
                self.connected = False
                self.socket = None
                self.log.info("Disconnected from Visitech light engine")
            except:
                self.connected = False
                self.socket = None
                self.log.info("Unable to disconnect from Visitech!")
            

    def send(self, data):
        """
        Send the data through the open TCP connection and return the
        reply from the Visitech.

        A string is always returned, with a default value of ''. A
        RuntimeError is raised if an error is detected in the response.
        """
        reply = None
        data += "\r\n\r\n"
        data = data.encode()
        self.log.debug("Sent:  '%s'", data.decode().rstrip())
        self.socket.sendall(data)
        try:
            reply = self.socket.recv(1024)
        except (OSError, socket.timeout):
            msg = "Visitech timed out!"
            self.log.critical(msg)
            self.shutdown(is_critical=True)
            sys.exit(msg)
        reply = reply.decode().split("\r\n")
        if "OK" not in reply[0]:
            raise RuntimeError(f"Error returned by light engine ({reply[1]}) {reply[2]}")
        self.log.debug("Reply: '%s'", reply[1])
        return reply[1]

    def load_defaults(self):
        """
        Load default values for LED driver. All values are defaulted on
        startup, so there is no need to run this command, unless the
        user wants to reload defaults values after adjustments.

        Return type +OK
        """
        return self.send("LOAD DEFAULTS")

    def set_static_ip(self, address):
        """
        Set a dedicated static IP address to the LRS. This IP address
        will be stored across power-offs and set on startup. Use the
        CIDR notation, e.g 192.168.0.20/24. The LRS is set from the
        factory to assign 192.168.0.10/24 to its interface in addition
        to use a DHCP address if a DHCP server exists on the network.
        Setting is immediate and no reboot is required.

        Return type +OK
        """
        return self.send(f"SET STATIC IP ADDR {address}")

    def get_version(self):
        """
        Get the version number of the firmware running on the LRS, in
        the format “1.1.0”. The version number is set when changes are
        made in according to these rules: Micro version is increased
        when a bug has been fixed. Minor version is increased when a new
        feature is added in a backwards compatible way. Major version is
        increased when new features or changes requires the API to be
        broken and the end-user will have to make changes accordingly in
        their own systems to suit.

        Return type +OK and version in format x.x.x
        """
        return self.send("GET VERSION")

    def led_driver_enable(self, led_num=0):
        """
        Turns on the LED driver. When on the LED driver will output
        current to the LED when a trigger pulse is received from the
        sequencer.

        Return type +OK
        """
        cmd = "SET LIGHT ON"
        if self.dual_led:
            cmd += f" {led_num}"
        return self.send(cmd)

    def led_driver_disable(self, led_num=0):
        """
        Turns off the LED driver. When off the LED driver will not
        output current to the LED, even when a trigger pulse is
        received.

        Return type +OK
        """
        cmd = "SET LIGHT OFF"
        if self.dual_led:
            cmd += f" {led_num}"
        return self.send(cmd)

    def get_led_driver_status(self, led_num=0):
        """
        Get the status of the LED on/off switch.

        Return type +OK
        <status>
        """
        cmd = "GET LIGHT STATUS"
        if self.dual_led:
            cmd += f" {led_num}"
        return self.send(cmd)

    def get_led_state(self, led_num=0):
        """
        Get the status of the light output. If the LED driver and the
        sequencer are turned on this command will wait for a few msec to
        see if the driver receives a trigger and successfully strobes.
        So when “ON” is returned, the LED has been outputting light
        since the command was executed. If the LED driver or sequencer
        is OFF then the command returns immediately with OFF as result.

        Return type +OK and ON or OFF
        """
        cmd = "GET LIGHT OUTPUT STATUS"
        if self.dual_led:
            cmd += f" {led_num}"
        return self.send(cmd)

    def set_led_amplitude(self, amplitude, led_num=0):
        """
        Set the amplitude value for the LED.

        Return type +OK and ON or OFF
        """
        cmd = "SET AMPLITUDE"
        if self.dual_led:
            cmd += f" {led_num}"
        cmd += f" {amplitude}"
        return self.send(cmd)

    def get_led_amplitude(self, led_num=0):
        """
        Get the current set amplitude value for the LED.

        Return type +OK and set value
        """
        cmd = "GET AMPLITUDE"
        if self.dual_led:
            cmd += f" {led_num}"
        return self.send(cmd)

    def set_led_driver_ocp(self, value, led_num=0):
        """
        Set the LED driver over-current protection value in Amps.

        Return type +OK
        """
        cmd = "SET OCP"
        if self.dual_led:
            cmd += f" {led_num}"
        cmd += f" {value}"
        return self.send(cmd)

    def get_led_driver_ocp(self, led_num=0):
        """
        Get the OCP value for the LED in Amps. Not recommended to adjust
        higher than default settings as this will lower the usable
        lifetime of the LED in the LRS engine.

        Return type +OK and set value
        """
        cmd = "GET OCP"
        if self.dual_led:
            cmd += f" {led_num}"
        return self.send(cmd)

    def set_led_driver_regulation_mode(self, mode, led_num=0):
        """
        Set the regulation mode to be used for controlling light output
        from LED. LIGHT is recommended. To be able to readout feedback
        for both current and light you must run it in COMBINED mode,
        this will regulate on light, but will sample both ADC’s.

        Options are: CURRENT, LIGHT, COMBINED

        Return type +OK
        """
        cmd = "SET REG MODE"
        if self.dual_led:
            cmd += f" {led_num}"
        cmd += f" {mode}"
        return self.send(cmd)

    def get_led_driver_regulation_mode(self, led_num=0):
        """
        Get the regulation mode to be used for controlling light output
        from the LED.

        Return type +OK and current set mode: CURRENT/LIGHT/COMBINED
        """
        cmd = "GET REG MODE"
        if self.dual_led:
            cmd += f" {led_num}"
        return self.send(cmd)

    def get_led_driver_current(self, led_num=0):
        """
        Get current passing through the LED driver on the last strobe in
        Amps.

        Return type +OK and feedback value as a floating point number
        """
        cmd = "GET CURRENT FEEDBACK"
        if self.dual_led:
            cmd += f" {led_num}"
        return self.send(cmd)

    def get_led_intensity(self, led_num=0):
        """
        Get the recorded light feedback value of the last strobe from
        the light sensors. This should correspond to the current
        amplitude set, if no protections have been triggered.

        Return type +OK and feedback value.
        """
        cmd = "GET LIGHT FEEDBACK"
        if self.dual_led:
            cmd += f" {led_num}"
        return float(self.send(cmd))

    def get_led_temp(self, led_num=0):
        """
        Get the LED temperature from the LED driver.

        Return type +OK and temperature value.
        """
        cmd = "GET LED TEMP"
        if self.dual_led:
            cmd += f" {led_num}"
        return float(self.send(cmd))

    def get_led_driver_board_temp(self, led_num=0):
        """
        Get the temperature of the LED driver board from the LED driver.

        Return type +OK and temperature value.
        """
        cmd = "GET BOARD TEMP"
        if self.dual_led:
            cmd += f" {led_num}"
        return float(self.send(cmd))

    def set_led_driver_board_temp_limit(self, temperature, led_num=0):
        """
        Set the temperature limit for the LED driver in Celsius. It is
        not recommended to exceed the default values as this will
        shorten the lifetime of the LED. Once the temperature is
        exceeded the light output is cut and a error is set in the
        sticky errors.

        Return type +OK
        """
        cmd = "SET BOARD TEMP LIMIT"
        if self.dual_led:
            cmd += f" {led_num}"
        cmd += f" {temperature}"
        return self.send(cmd)

    def get_led_driver_board_temp_limit(self, led_num=0):
        """
        Get the temperature limit for the LED driver in Celsius.

        Return type +OK and board temperature limit in Celsius
        """
        cmd = "GET BOARD TEMP LIMIT"
        if self.dual_led:
            cmd += f" {led_num}"
        return float(self.send(cmd))

    def set_led_temp_limit(self, temperature, led_num=0):
        """
        Set the temperature limit for the LED in Celsius. It is not
        recommended to exceed the default values as this will shorten
        the lifetime of the LED. Once the temperature is exceeded the
        light output is cut and a error is set in the sticky errors.

        Return type +OK
        """
        cmd = "SET LED TEMP LIMIT"
        if self.dual_led:
            cmd += f" {led_num}"
        cmd += f" {temperature}"
        return self.send(cmd)

    def get_led_temp_limit(self, led_num=0):
        """
        Get the temperature limit for the LED in Celsius.

        Return type +OK and board temperature limit in Celsius
        """
        cmd = "GET LED TEMP LIMIT"
        if self.dual_led:
            cmd += f" {led_num}"
        return self.send(cmd)

    def start_sequencer(self):
        """
        Turn the sequencer on.

        Return type +OK
        """
        return self.send("SET SEQ ON")

    def stop_sequencer(self):
        """
        Turn the sequencer off.

        Return type +OK
        """
        if self.socket is not None:
            self.led_on = False
            return self.send("SET SEQ OFF")
        return ""

    def pause_sequencer(self):
        """
        Pause the sequencer.

        Return type +OK
        """
        return self.send("SET SEQ PAUSE")

    def get_dmd_status(self):
        """
        Get overview of DMD states. Such as sequencer running state.
        The result is returned as a JSON dictionary.

        Return type +OK and JSON dictionary

        Example:
        GET DMD STATUS
        +OK
        {
            "dmd_mirrors_parked": false
            "dmd_reset_controller_error": false
            "external_video_source_locked": true
            "forced_swap_error": false
            "internal_initialization": true
            "internal_memory_test_passed": true
            "port_1_syncs_valid": true
            "port_2_syncs_valid": false
            "sequencer_abort_flag": false
            "sequencer_error": false
            "sequencer_running": false
            "video_frozen": false
        }
        """
        return json.loads(self.send("GET DMD STATUS").replace("\n    ", ""))

    def set_dmd_operation_mode(self, mode):
        """
        Set the operation mode of the DMD.

        Available modes:
        -VIDEO_MODE - not documented in API but present
        -VIDEO_PATTERN_MODE - Use video input, must define pattern LUT
          also. To enable this mode the HDMI or Displayport must be
          inited before setting mode.
        -PATTERN_ON_THE_FLY_MODE - Upload images via this protocol.

        Return type +OK
        """
        time.sleep(5)  # must wait for at least 5 seconds to read or write operation mode
        return self.send(f"SET OPERATION MODE {mode}")

    def get_dmd_operation_mode(self):
        """
        Get the current operation mode of the DMD.

        Return type +OK and mode
        """
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
        """
        Set the LUT definition of the DMD controller. Each line
        represents one pattern. Parameters are seperated by comma and
        are as follows:
        -PATTERN_EXPOSURE_MICROSECOND - uSec time for the pattern to be
          displayed for entry.
        -DARK_TIME - uSec time after PATTERN_EXPOSURE_MICROSECOND to
          display a dark pattern.
        -CLEAR_PATTERN - Clear the pattern after exposure. This is only
          applicable for 1 bit patterns with an external trigger. For
          other patterns, the clear is automatically handled.
        -BIT_DEPTH - Bit depth of pattern. 1-8 is acceptable. For black
          and white use 1-bit (1).
        -WAIT_FOR_TRIGGER - Wait for trigger before displaying the
          pattern, or continue runnning.
        -IMAGE_PATTERN_INDEX - Only applies to PATTERN_ON_THE_FLY_MODE
          operation mode: The image pattern to load from memory to DMD
          for entry.
        -IMAGE_PATTERN_BIT_INDEX - The bit layer of the pattern to load.
          E.g for 1-bit depth patterns we can display 24 patterns
          seperately from a uploaded 24-bit bitmap, by increasing the
          bit index. 0-23 is acceptable.

        Example input with 1 sequence:

        SET LUT DEFINITION
        10000,500,1,1,1,1,1

        For now we will only support one sequence at a time.

        Return type +OK
        """
        cmd = f"SET LUT DEFINITION\r\n{exposure},{darktime},{clear},{bitdepth},"
        cmd += f"{wait_for_trigger},{pattern_index},{bit_index}"
        return self.send(cmd)

    def set_sequencer_lut_config(self, num_sequences=1, repeats=1):
        """
        Set the LUT config of the DMD controller. Parameters are entries
        in the LUT definition to be used, and x amount of repeats.

        NOTE: The DLPC docs say to do this before setting the definition
        above, but they lie, you have to do this after, before starting
        the sequencer.

        Return type +OK
        """
        return self.send(f"SET LUT CONFIG {num_sequences} {repeats}")

    def upload_image(self, pattern_index, bitmap_size, bitmap_data):
        """
        Upload 24-bit bitmap to DMD controller. Non-compressed, with a
        standard header bitmap must be used. Keep in mind that a 24-bit
        bitmap can contain 24x 1-bit bitmaps if black&white exposure is
        done. This request is special in that it will have multiple
        double line shifts. The pattern index and bitmap size in bytes
        must be followed by double CRLF before image data is sent.

        Example:

        UPLOAD IMAGE PATTERN
        <PATTERN INDEX>
        <BITMAP SIZE IN BYTES>
        <BINARY BITMAP DATA>

        Return type +OK
        """
        return self.send(
            f"UPLOAD IMAGE PATTERN\r\n{pattern_index}\r\n{bitmap_size}\r\n{bitmap_data}"
        )

    def set_video_source(self, source="HDMI"):
        """
        Set the current input source for the video input. Input source
        must be set before operation mode is changed to video type.

        Currently the only externally available source is HDMI

        Return type +OK
        """
        # workaround for incorrect API - SET VIDEO SOURCE wasn't actually implemented
        # return self.send(f"SET INPUT SOURCE {source}")
        if source == "DISPLAYPORT":
            return self.send("INIT DISPLAYPORT")
        return self.send("INIT HDMI")

    def get_video_source(self):
        """
        Get the current input source for the video input.

        Return type +OK and source: HDMI/DISPLAYPORT/NONE
        """
        # workaround for incorrect API - command was documented incorrectly
        # return self.send("GET VIDEO SOURCE")
        return self.send("GET INPUT SOURCE")

    def set_pixel_mode(self, mode):
        """
        Set pixel mode used by sequencer.

        Available modes:
        -data_port1_single_pixel_mode 0
        -data_port2_single_pixel_mode 1
        -data_port1_2_dual_pixel_mode 2
        -data_port2_1_dual_pixel_mode 3

        Return type +OK
        """
        return self.send(f"SET PIXEL MODE {mode}")

    def park_dmd_mirrors(self):
        """
        Park the DMD mirrors to a flat position.

        This should be handled automatically. The current state of the
        mirrors is indicated in get_dmd_status()

        Return type +OK
        """
        return self.send("SET MIRRORS PARKED")

    def unpark_dmd_mirrors(self):
        """
        Unark the DMD mirrors.

        If the mirrors are parked, they will need to be unparked before
        exposures can happen. The current state of the mirrors is
        indicated in get_dmd_status()

        Return type +OK
        """
        return self.send("SET MIRRORS UNPARKED")

    def get_sticky_errors(self, warn="ALL"):
        """
        Sticky errors are used to indicate that a runtime protection
        were triggered since last reading the errors. Such as the LED
        over-current protection. Once the values are read the errors are
        reset, they can however be triggered immediately after clearing
        if the error state is still apparent. The errors are reported
        with a CRLF seperating each. There can be multiple errors
        reported at once.

        Available errors:
        -BOARD TEMPERATURE LIMIT EXCEEDED - Board temperature protection
          has been exceeded.
        -LED TEMPERATURE LIMIT EXCEEDED - LED temperature protection has
          been exceeded.
        -DOOR SWITCH OPEN CIRCUIT - Door safety switch is open, no light
          output will be generated.
        -LED OVER CURRENT PROTECTION TRIGGERED - LED over current
          triggered. Raise OCP value or lower LED amplitude.

        Return type +OK and one line per error triggered since last
        reading
        """
        errors = self.send("GET STICKY ERRORS").split("\n")
        if errors:
            for error in errors:
                if error:
                    if warn is "ALL":
                        if error.lower() == "led over current protection triggered":
                            if self.suppress_ocp_error:
                                self.suppress_ocp_error = False  # only do this once per print
                        else:
                            self.log.warning("Visitech Error: %s", error)  # report other errors
                    elif warn is "TEMP":
                        # Suppress the first Visitech OCP error. This appears to always be
                        # triggered on the first exposure of each print job. It would be better
                        # to figure out why this happens in the hardware and fix it there.
                        if error.lower() != "led over current protection triggered" and error.lower() != "door switch open circuit":
                            self.log.warning("Visitech Error: %s", error)  # report other errors
                    elif warn is "NONE":
                        self.log.info(error.capitalize())
        return errors

    def get_logs(self):
        """
        Get events logged by the LRS during runtime. Each log line is
        seperated by a CR LF. Each column is seperated by a dash (-).

        Return type +OK and one line per event triggered since last
        reading
        """
        return self.send("GET LOGS")

    def get_normalization_factor(self):
        """
        Return the normalization factor.

        The normalization factor is used by the Visitech firmware when
        correlating the set power value and the output optical power.
        This is usually calibrated in factory by Visitech, but we may
        want to use it ourselves to get consistient output power across
        multiple printers, i.e. make it so a power setting of 100
        correlates to the same output optical power in each light engine

        Return type +OK and normalization factor value as a floating
        point number
        """
        return float(self.send("FACTORY GET NORMALIZATION VALUE"))

    def set_normalization_factor(self, normalization_factor):
        """
        Set the normalization factor.

        See get_normalization_factor for more details.

        Return type +OK
        """
        return self.send(f"FACTORY SET NORMALIZATION VALUE {normalization_factor}")

    def split_exposure_time(self, exposure):
        """
        Split a long exposure time into an array of smaller exposure
        times.
        """
        n = int(exposure // self.max_exp_time)
        if exposure % self.max_exp_time != 0:
            exposure = [self.max_exp_time] * n + [exposure % self.max_exp_time]
        else:
            exposure = [self.max_exp_time] * n
        return exposure

    def read_all_status(self, warn="ALL"):
        """
        Return commonly queried status.
        """
        dict = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "led_feedback": self.get_led_intensity(),
            "led_temp": self.get_led_temp(),
            "led_driver_temp": self.get_led_driver_board_temp(),
            "led_sticky_errors": self.get_sticky_errors(warn),
            "led_driver_status": self.get_led_driver_status(),
        }
        if self.dual_led:
            dict["led_feedback2"] = self.get_led_intensity(led_num=1)
            dict["led_temp2"] = self.get_led_temp(led_num=1)
            dict["led_driver_temp2"] = self.get_led_driver_board_temp(led_num=1)
            dict["led_driver_status2"] = self.get_led_driver_status(led_num=1)
        return dict

    def setup_exposure(self, exposure_time_ms, led_power=100, repeat=1, led_num=0):
        """
        Setup an exposure.
            exposure_time_ms - exposure time in milliseconds
            led_power - power setting
            repeat - number of repeats
        """
        self.exposure_time = exposure_time_ms

        if self.dual_led:
            if led_num == 0:
                self.led_driver_enable(led_num=0)
                self.led_driver_disable(led_num=1)
            else:
                self.led_driver_enable(led_num=1)
                self.led_driver_disable(led_num=0)

        min_t = 4.046
        max_t = 10000
        self.log.info(
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

    def perform_exposure(self):
        """
        Start an exposure.
        """
        self.led_on = True
        if self.exposure_time != 0:
            self.log.info("Exposing for %s ms", self.exposure_time)
            self.start_sequencer()
            time.sleep(self.exposure_time * 1e-3)
        self.led_on = False

    def project(self, exposure, power, repeats=1, led_num=0):
        """
        Call all of the necessary methods to project an image, and block
        until projection is complete.
        """

        self.log.info(
            "Exposing %s for %s ms at power setting %s. Repeat %s",
            self.leds[led_num],
            exposure,
            power,
            repeats,
        )

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
            # this provides the minimum blanking of 233 us of the full 33333 us cycle
            # (at 30Hz on HDMI)
            self.set_sequencer_lut_definition(33100, 0, 0, 8, 0, 0, 0)
            self.set_sequencer_lut_config(repeats=0)
            self.start_sequencer()  # sequencer will be stopped on program exit
        else:  # normal display is desired
            for t in self.split_exposure_time(exposure):
                # the TI board expects exposure in microseconds
                self.set_sequencer_lut_definition(exposure=int(t * 1000))
                self.set_sequencer_lut_config(repeats=repeats)
                self.start_sequencer()
                time.sleep(t * 1e-3)
                self.led_on = False
