# -*- coding: utf-8 -*-
"""
Projector
=========
"""
import time
import atexit
import socket
from pathlib import Path
from datetime import datetime

from .screen import ScreenThread

# pylint:disable=too-many-public-methods
class Projector:
    """
    This is the new VIsitech driver which runs based on their Ethernet interface and API.
    Commands are sent over a TCP connection.

    Here is a list of possible errors for different commands:

    - NOT_CONNECTED -1 Lost connection with onboard DLP controller or LED driver.
    - OUT_OF_MEMORY -2 Onboard computer out of memory.
    - OPEN_DEVICE_FAILED -3 Could not open device for writing.
    - I2C_SEND_FAILED -4 I2C communication with onboard controller failed.
    - I2C_READ_FAILED -5 I2C communication with onboard controller failed.
    - I2C_DEVICE_LIST_FAILED -6 Could not enumerate I2C devices on bus.
    - I2C_DEVICE_LIST_EMPTY -7 I2C device list is empty.
    - I2C_READ_SHORT -8 I2C communication corrupt, read were too short.
    - I2C_WRITE_SHORT -9 I2C communication corrupt, write were too short.
    - I2C_MASTER_SET_FAIL -10 I2C communication issue, could not set self as bus master.
    - TO_HIGH_LED_AMPLITUDE -11 LED amplitude value too high to set. 0-2000 is acceptable range.
    - SEQUENCE_FILE_ERROR -12 Sequence file is not valid.
    - SEQUENCE_NUM_ARGS -13 Sequence file has too many arguments.
    - SEQUENCE_TOO_MANY_PATTERNS -14 Sequence file has too many patterns.
    - STRESS_TEST_FAILED -15 Stress test has failed.
    - ARGUMENT_INVALID -16 Argument is invalid.
    - ARGUMENT_OUT_OF_RANGE -17 Argument is out of range.
    - TEST_FAILED -19 Self test has failed.
    - DEVICE_COMMUNICATION_FAILED -20 Internal communication error.
    - OPEN_FILE_FAILED -21 Could not open internal file. SD card may be corrupt.
    - INVALID_ARGUMENT -1000 Invalid serialization protocol argument sent.
    - INVALID_COMMAND -1001 Invalid serialization protocol command sent.
    - RUNTIME_ERROR -1002 Unknown runtime error. See message.
    - I2C_BUS_DOWN -1003 Onboard CPU is not connected to any devices.

    These error codes will also appear when using GET LOGS if any is available.

    There are two commands not documented in the API but are present on the device that I have implemented:

    GET LED TEMP
    GET BOARD TEMP

    There are several commands not documented in the API but are present on the device that I have not
    implemented. I am not sure what these do and they shouldn't be used:

    PING
    GET LBREG
    SET LBREG
    FACTORY SET NORMALIZATION VALUE

    There are two commands in the API that are incorrect:

    SET INPUT SOURCE - not implemented at all - replaced with INIT HDMI and INIT DISPLAYPORT
    GET INPUT SOURCE - actually implemented as GET VIDEO SOURCE

    """

    def __init__(self, resolution, fullscreen=True):
        self.resolution = resolution
        self.fullscreen = fullscreen
        self.max_exp_time = 10000  # max single projection time in ms

        # setup TCP connection
        self.host = "192.168.0.10"
        self.port = 5000
        self.socket = (
            None  # start as None so we can tell if a connection has been attempted
        )
        self.tcp_log = (
            Path.cwd() / "logs"
        )  # a log to track all TCP communications for debugging, gets created on connect

        # setup screen thread
        self.screenThread = ScreenThread(self.resolution, self.fullscreen)

        # register exit handlers
        atexit.register(self.disconnect)  # close the TCP conenction on exit
        atexit.register(self.stop_sequencer)  # make sure DMD is stopped on exit

    def connect(self, attempts=10, timeout=1):
        print("Connecting to light engine, this may take up to 1 minute...")

        # start TCP connection
        i = 0
        connected = False
        while i < attempts:  # try up to attempts number of times to create a connection
            i += 1
            try:  # attempt a new connection
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((self.host, self.port))
                connected = True
            except OSError as e:
                print("{}. Retrying in {} second(s)".format(e, timeout))
                self.socket = None  # get rid of handle to bad socket
                time.sleep(timeout)  # wait to try again
        if not connected:  # connection failed every time, notify user
            print("Light engine not found. It it plugged in and powered on?")
            exit("Light engine not found. It it plugged in and powered on?")

        # Create log
        date_and_time = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
        self.tcp_log = str(
            self.tcp_log / "light_engine_TCP_dump_{}.txt".format(date_and_time)
        )

        # start screen thread
        self.screenThread.start()

        # set default state for light engine
        self.set_video_source("HDMI")
        self.set_led_driver_regulation_mode("LIGHT")
        self.set_dmd_operation_mode("VIDEO_PATTERN_MODE")

    def disconnect(self):
        if self.socket is not None:
            self.socket.close()

    def send(self, data):
        """
        Send the data through the open TCP connection.

        Returns the reply from the Projector, with the +OK stripped if present. Error codes
        will remain in the output if present.

        """
        reply = None
        with open(self.tcp_log, "a") as f:
            data += "\r\n\r\n"
            data = data.encode()
            f.write("Sent : {}\n".format(data))

            # transmit data and read response
            self.socket.sendall(data)
            reply = self.socket.recv(1024)
            f.write("Reply: {}\n".format(reply))
            reply = str(reply.decode())
            # print('Sent', repr(data))
            # print('Reply', repr(reply.decode()))
            print("Sent :", str(data).replace("\r\n", " "))
            print("Reply:", reply.replace("\r\n", " "))
        return reply

    def load_defaults(self):
        """
        Load default values for LED driver. All values are defaulted on startup, so there is no need to run this
        command, unless the user wants to reload defaults values after adjustments.

        Return type +OK
        """
        return self.send("LOAD DEFAULTS")

    def set_static_ip(self, address):
        """
        Set a dedicated static IP address to the LRS. This IP address will be stored across power-offs and set
        on startup. Use the CIDR notation, e.g 192.168.0.20/24. The LRS is set from the factory to assign
        192.168.0.10/24 to its interface in addition to use a DHCP address if a DHCP server exists on the
        network. Setting is immediate and no reboot is required.

        Return type +OK
        """
        return self.send("SET STATIC IP ADDR {}".format(address))

    def get_version(self):
        """
        Get the version number of the firmware running on the LRS, in the format “1.1.0”. The version number
        is set when changes are made in according to these rules: Micro version is increased when a bug
        has been fixed. Minor version is increased when a new feature is added in a backwards compatible
        way. Major version is increased when new features or changes requires the API to be broken and the
        end-user will have to make changes accordingly in their own systems to suit.

        Return type +OK and version in format x.x.x
        """
        return self.send("GET VERSION")

    def led_driver_enable(self):
        """
        Turns on the LED driver. When on the LED driver will output current to the LED when a trigger
        pulse is received from the sequencer.

        Return type +OK
        """
        return self.send("SET LIGHT ON")

    def led_driver_disable(self):
        """
        Turns off the LED driver. When off the LED driver will not output current to the LED, even when a
        trigger pulse is received.

        Return type +OK
        """
        return self.send("SET LIGHT OFF")

    def get_led_driver_status(self):
        """
        Get the status of the LED on/off switch.

        Return type +OK
        <status>
        """
        return self.send("GET LIGHT STATUS")

    def get_led_state(self):
        """
        Get the status of the light output. If the LED driver and the sequencer is turned on this command will
        wait for a few msec to see if the driver receives a trigger and successfully strobes. So when “ON”
        is returned the LED has been outputting light since the command were executed. If LED driver or
        sequencer is OFF then the command returns immediately with OFF as result.

        Return type +OK and ON or OFF
        """
        return self.send("GET LIGHT OUTPUT STATUS")

    def set_led_amplitude(self, amplitude):
        """
        Set the amplitude value for the LED.

        Return type +OK and ON or OFF
        """
        return self.send("SET AMPLITUDE {}".format(amplitude))

    def get_led_amplitude(self):
        """
        Get the current set amplitude value for the LED.

        Return type +OK and set value
        """
        return self.send("GET AMPLITUDE")

    def set_led_driver_ocp(self, value):
        """
        Set the LED driver over-current protection value in Amps.

        Return type +OK
        """
        return self.send("SET OCP {}".format(value))

    def get_led_driver_ocp(self):
        """
        Get the OCP value for the LED in Amps. Not recommended to adjust higher than default settings.
        This will lower the usable life-time of the LED in the LRS engine.

        Return type +OK and set value
        """
        return self.send("GET OCP")

    def set_led_driver_regulation_mode(self, mode):
        """
        Set the regulation mode to be used for controlling light output from LED. LIGHT is recommended.
        To be able to readout feedback for both current and light you must run it in COMBINED mode, this
        will regulate on light, but will sample both ADC’s.

        Options are: CURRENT, LIGHT, COMBINED

        Return type +OK
        """
        return self.send("SET REG MODE {}".format(mode))

    def get_led_driver_regulation_mode(self):
        """
        Get the regulation mode to be used for controlling light output from LED.

        Return type +OK and current set mode: CURRENT/LIGHT/COMBINED
        """
        return self.send("GET REG MODE")

    def get_led_driver_current(self):
        """
        Get current passing through the LED driver on the last strobe in Amps.

        Return type +OK and feedback value as a floating point number
        """
        return self.send("GET CURRENT FEEDBACK")

    def get_led_intensity(self):
        """
        Get the recorded light feedback value of the last strobe from the light sensors. This should correspond
        to the current amplitude set, if not any protections have been triggered.

        Return type +OK and feedback value.
        """
        return self.send("GET LIGHT FEEDBACK")

    def get_led_temp(self):
        """
        Get the LED temperature from the LED driver.

        Return type +OK and temperature value.
        """
        return self.send("GET LED TEMP")

    def get_led_driver_board_temp(self):
        """
        Get the temperature of the LED driver board from the LED driver.

        Return type +OK and temperature value.
        """
        return self.send("GET BOARD TEMP")

    def set_led_driver_board_temp_limit(self, temperature):
        """
        Set the temperature limit for the LED driver in Celsius. It is not recommended to exceed the default
        values as this will shorten the life-time of the LED. Once the temperature is exceeded the light output
        is cut and a error is set in the sticky errors.

        Return type +OK
        """
        return self.send("SET BOARD TEMP LIMIT {}".format(temperature))

    def get_led_driver_board_temp_limit(self):
        """
        Get the temperature limit for the LED driver in Celsius.

        Return type +OK and board temperature limit in Celsius
        """
        return self.send("GET BOARD TEMP LIMIT")

    def set_led_temp_limit(self, temperature):
        """
        Set the temperature limit for the LED in Celsius. It is not recommended to exceed the default values
        as this will shorten the life-time of the LED. Once the temperature is exceeded the light output is cut
        and a error is set in the sticky errors.

        Return type +OK
        """
        return self.send("SET LED TEMP LIMIT {}".format(temperature))

    def get_led_temp_limit(self):
        """
        Get the temperature limit for the LED in Celsius.

        Return type +OK and board temperature limit in Celsius
        """
        return self.send("GET LED TEMP LIMIT")

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
        # since this always gets run on exit, check to make sure a connection was made
        if self.socket is not None:
            return self.send("SET SEQ OFF")

    def pause_sequencer(self):
        """
        Pause the sequencer.

        Return type +OK
        """
        return self.send("SET SEQ PAUSE")

    def get_dmd_status(self):
        """
        Get overview of DMD states. Such as sequencer running state. The result is returned as JSON.

        Return type +OK and JSON string

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
        return self.send("GET DMD STATUS")

    def set_dmd_operation_mode(self, mode):
        """
        Set the operation mode of the DMD.

        Available modes:
        -VIDEO_MODE - not documented in API but present
        -VIDEO_PATTERN_MODE - Use video input, must define pattern LUT also. To enable this mode the
        HDMI or Displayport must be inited before setting mode.
        -PATTERN_ON_THE_FLY_MODE - Upload images via this protocol.

        Return type +OK
        """
        time.sleep(5)  # must wait for at least 5 seconds to read or write operation mode
        return self.send("SET OPERATION MODE {}".format(mode))

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
        bitdepth=7,
        wait_for_trigger=1,
        pattern_index=0,
        bit_index=0,
    ):
        """
        Set the LUT definition of the DMD controller. Each line represents one pattern. Parameters are
        seperated by comma and are as following:
        -PATTERN_EXPOSURE_MICROSECOND - uSec time for the pattern to be displayed for entry.
        -DARK_TIME - uSec time after PATTERN_EXPOSURE_MICROSECOND to display a dark pattern.
        -CLEAR_PATTERN - Clear the pattern after exposure. This is only applicable for 1 bit patterns with an
        external trigger. For other patterns, the clear is automatically handled.
        -BIT_DEPTH - Bit depth of pattern. 1-8 is acceptable. For black&white use 1-bit (1).
        -WAIT_FOR_TRIGGER - Wait for trigger before displaying the pattern, or continue runnning.
        -IMAGE_PATTERN_INDEX - Only applies to PATTERN_ON_THE_FLY_MODE operation mode: The
        image pattern to load from memory to DMD for entry.
        -IMAGE_PATTERN_BIT_INDEX - The bit layer of the pattern to load. E.g for 1-bit depth patterns we
        can display 24 patterns seperately from a uploaded 24-bit bitmap, by increasing the bit index. 0-23 is
        acceptable.

        Example input with 1 sequence:

        SET LUT DEFINITION
        10000,500,1,1,1,1,1

        For now we will only support one sequence at a time.

        Return type +OK
        """

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
        """
        Set the LUT config of the DMD controller. Parameters are entries in the LUT definition to be used,
        and x amount of repeats.

        NOTE: The DLPC docs say to do this before setting the definition above, but they lie, you have to
        do this after, before starting the sequencer.

        Return type +OK
        """
        return self.send("SET LUT CONFIG {} {}".format(num_sequences, repeats))

    def upload_image(self, pattern_index, bitmap_size, bitmap_data):
        """
        Upload 24-bit bitmap to DMD controller. Non-compressed, with a standard header bitmap must be
        used. Keep in mind that a 24-bit bitmap can contain 24x 1-bit bitmaps if black&white exposure is
        done. This request is special in that it will have multiple double line shifts. The pattern index and
        bitmap size in bytes must be followed by double CRLF before image data is sent.

        Example:

        UPLOAD IMAGE PATTERN
        <PATTERN INDEX>
        <BITMAP SIZE IN BYTES>
        <BINARY BITMAP DATA>

        Return type +OK
        """
        return self.send(
            "UPLOAD IMAGE PATTERN\r\n{}\r\n{}\r\n{}".format(
                pattern_index, bitmap_size, bitmap_data
            )
        )

    def set_video_source(self, source="HDMI"):
        """
        Set the current input source for the video input. Input source must be set before operation mode is
        changed to video type.

        Currently the only externally available source is HDMI

        Return type +OK
        """
        # workaround for incorrect API - SET VIDEO SOURCE wasn't actually implemented
        # return self.send("SET INPUT SOURCE {}".format(source))
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
        return self.send("SET PIXEL MODE {}".format(mode))

    def get_sticky_errors(self):
        """
        Sticky errors are used to indicate that a runtime protection were triggered since last reading the
        errors. Such as the LED over-current protection. Once the values are read the errors are reset, they
        can however be triggered immediately after clearing if the error state is still apparent. The errors are
        reported with a CRLF seperating each. There can be multiple errors reported at once.

        Available errors:
        -BOARD TEMPERATURE LIMIT EXCEEDED - Board temperature protection has been exceeded.
        -LED TEMPERATURE LIMIT EXCEEDED - LED temperature protection has been exceeded.
        -DOOR SWITCH OPEN CIRCUIT - Door switch safety switch is in open-circuit, no light output will be
        generated.
        -LED OVER CURRENT PROTECTION TRIGGERED - LED over current triggered. Raise OCP value or
        lower LED amplitude.

        Return type +OK and one line per error triggered since last reading
        """
        return self.send("GET STICKY ERRORS")

    def get_logs(self):
        """
        Get events logged by the LRS during runtime. Each log line is seperated by a CR LF. Each column
        is seperated by a dash (-).

        Return type +OK and one line per event triggered since last reading
        """
        return self.send("GET LOGS")

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

    def clear_image(self):
        """
        Blank the virtual screen that provides the image to the projector.
        Sets full image to black.
        """
        self.screenThread.screen.clear()

    def project(self, image, exposure, power, repeats=1):
        """
        Call all of the necessary methods to project an image, and block until projection
        is complete.
        """
        print("start exposure")
        self.set_led_amplitude(power)
        print("exp time", exposure)

        if repeats == 0:  # if continuous display is desired
            self.set_sequencer_lut_definition(
                33100, 0, 0, 7, 0, 0, 0
            )  # this provides the minimum blanking of 233 us of the full 33333 us cycle (at 30Hz on HDMI)
            self.set_sequencer_lut_config(repeats=repeats)  # 0 means repeat forever
            self.screenThread.screen.draw(image)  # draw to virtual screen
            self.start_sequencer()  # start the sequencer and don't stop it (will be stopped on program exit)
        else:  # normal display is desired
            for t in self.split_exposure_time(exposure):
                self.set_sequencer_lut_definition(
                    exposure=t * 1000
                )  # the TI board expects exposure in microseconds
                self.set_sequencer_lut_config(
                    repeats=repeats
                )  # set the number of repetitions
                self.screenThread.screen.draw(image)  # draw to the virtual screen
                time.sleep(0.1)
                self.start_sequencer()  # start the sequencer
                time.sleep(0.1 + t * 1e-3)
                self.stop_sequencer()  # stop the sequencer
                self.clear_image()

    def projectMulti(self, images, exposureTimes, ledPowers):
        """Project multiple images with its own expoure time and
        and LED power setting.

        :param list images: a list of image filenames
        :param list exposureTimes: a list of exposure times (ms)
        :param list ledPowers: a list of led power settings
                            (0-1000)
        """
        for image, expTime, power in zip(images, exposureTimes, ledPowers):
            self.project(image, expTime, power)


if __name__ == "__main__":
    projectorResolution = (2560, 1600)
    p = Projector(projectorResolution)
    p.project("images/calibrate.png", exposure=1000, power=100)
