
# -*- coding: utf-8 -*-
"""
Projector
=========
"""
import time
import atexit
import socket
from .projector_screen import ScreenThread


# host = "192.168.0.10"
# print("Host", host)
# port = 5000                   # The same port as used by the server
# s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# s.connect((host, port))
# s.sendall(b'"SET AMPLITUDE 100\r\n\r\n')
# data = s.recv(1024)
# s.close()
# print('Received', repr(data))



class Visitech:
    def __init__(self, resolution, fullscreen=True):
        self.resolution = resolution
        self.fullscreen = fullscreen
        self.screenThread = None
        # self.i2c = LightEngineI2C()

        # start TCP connection with default settings
        self.host = "192.168.0.10"
        self.port = 5000
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        atexit.register(self.socket.close)              # close the TCP conenction on exit
        atexit.register(self.start_sequencer)           # make sure DMD is stopped on exit

    def send(self, data):
        """
        Send the data through the open TCP connection.

        Returns the reply from the Visitech
        """

        self.socket.sendall(data + "\r\n\r\n")
        reply = self.socket.recv(1024)
        print('Received', repr(data))
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
        Get the version number of the firmware running on the LRS, in the format “1.1.0”. The version number is set when changes are made in according to these rules: Micro version is increased when a bug
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
        return self.send("GET VERSION")

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
        -VIDEO_PATTERN_MODE - Use video input, must define pattern LUT also. To enable this mode the
        HDMI or Displayport must be inited before setting mode.
        -PATTERN_ON_THE_FLY_MODE - Upload images via this protocol.

        Return type +OK
        """
        return self.send("SET OPERATION MODE {}".format(mode))

    def get_dmd_operation_mode(self):
        """
        Get the current operation mode of the DMD.

        Return type +OK and mode
        """
        return self.send("")

    # pylint: disable=too-many-arguments
    def set_sequencer_lut_definition(self, exposure, darktime=0, clear=1, bitdepth=7, wait_for_trigger=1, pattern_index=1, bit_index=0):
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

        return self.send("SET LUT DEFINITION\r\n{},{},{},{},{},{},{}".format(exposure, darktime, clear, bitdepth, wait_for_trigger, pattern_index, bit_index))

    def set_sequencer_lut_config(self, num_sequences=1, repeats=1):
        """
        Set the LUT config of the DMD controller. Parameters are entries in the LUT definition to be used,
        and x amount of repeats.

        NOTE: The DLPC docs say to do this before setting the definition above, but they lie, you have to
        do this after, before starting the sequencer.

        Return type +OK
        """
        return self.send("SET LUT CONFIG {} {}".format(num_sequences, repeats))

    def function_name(self, pattern_index, bitmap_size, bitmap_data):
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
        return self.send("UPLOAD IMAGE PATTERN\r\n{}\r\n{}\r\n{}".format(pattern_index, bitmap_size, bitmap_data))

    def set_video_source(self, source="HDMI"):
        """
        Set the current input source for the video input. Input source must be set before operation mode is
        changed to video type.

        Currently the only externally available source is HDMI

        Return type +OK
        """
        return self.send("SET INPUT SOURCE {}".format(source))

    def get_video_source(self):
        """
        Get the current input source for the video input.

        Return type +OK and source: HDMI/DISPLAYPORT/NONE
        """
        return self.send("GET VIDEO SOURCE")

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

    # def projectMulti(self, images, exposureTimes, ledPowers):
    #     """Project multiple images with its own expoure time and
    #     and LED power setting.

    #     :param list images: a list of image filenames
    #     :param list exposureTimes: a list of exposure times (ms)
    #     :param list ledPowers: a list of led power settings
    #                            (0-1000)
    #     """
    #     for im, exposureTime, ledPower in zip(images, exposureTimes, ledPowers):
    #         self.project(im, exposureTime, ledPower)

    # def project(self, image, exposureTime, ledPower):
    #     """Poject a image for a period of t (ms).

    #     :param image: an 8-bit grayscale image filename
    #     :param int exposureTime: exposure time (ms)
    #     :param int ledPower: LED power setting (0-1000)
    #     """
    #     max_time = 10000
    #     n = int(exposureTime // max_time)
    #     if exposureTime % max_time != 0:
    #         exposureTime = [max_time] * n + [exposureTime % max_time]
    #     else:
    #         exposureTime = [max_time] * n

    #     if ledPower != self.ledPower:
    #         self.setLedAmplitude(ledPower)

    #     for t in exposureTime:
    #         self.sendSequence(t)
    #         self.screenThread.screen.draw(image)
    #         time.sleep(0.1)
    #         self.start()
    #         time.sleep(0.1 + t * 1e-3)
    #         self.stop()

    # # pylint: disable=unused-argument, unused-variable, too-many-arguments, no-self-use
    # def sendSequence(self, exposure, repeat=1, bitdepth=7, vsync=1, darktime=0, bitposition=0):
    #     """Generate and send control sequence

    #     :param int exposure: exposure time (ms)
    #     :param int repeat: number of times to repeat pattern sequence
    #                        0 - repeat forever, (1-4294967296) - repeat
    #                        n times
    #     :param int bitdepth: image bit depth. 7 means 8 bits
    #     :param int vsync: 1 = Wait for VSYNC before displaying the
    #                       pattern, 0 = Continue running after previous
    #                       pattern
    #     :param int darktime: (0-2^24) Dark display time following exposure
    #     :param int bitposition: see DLPC900 datasheet

    #     """
    #     exptime = int(exposure * 1e3)   # convert to us
    #     sequence = [[exptime, bitdepth, 1, vsync, darktime, bitposition, 0]]
    #     # self.i2c.parseSendSequence(sequence, repeat)

    # def calibrateProject(self, image, ledPower, repeat, exposureTime):
    #     """Enable continuous projection of an image for
    #     calibration

    #     :param image: an 8-bit grayscale image filename
    #     :param int ledPower: LED power setting (0-1000)
    #     :param int repeat: 0 repeats forever, 1 repeat
    #                        once (normal operation)
    #     :param int exposureTime: exposure time (ms).
    #     """
    #     if repeat != 0:
    #         self.project(image, exposureTime, ledPower)
    #     else:
    #         self.setLedAmplitude(ledPower)
    #         self.sendSequence(exposureTime, repeat)
    #         self.screenThread.screen.draw(image)
    #         time.sleep(0.1)
    #         self.start()

    # def clear(self):
    #     """Clear the projector screen to be black"""
    #     self.screenThread.screen.clear()

if __name__ == '__main__':
    projectorResolution = (2560, 1600)
    p = Visitech(projectorResolution)
    # p.calibrateProject("calibrate.png", 100, 0, 1000)
