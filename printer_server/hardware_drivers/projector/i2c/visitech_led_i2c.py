import json
import logging
from binascii import hexlify

from .i2c import I2C

# defaults
LED_I2C_ADDR = 0x22
OCP_AMP_PER_UNIT_HW_VER1 = 0.196
DEF_PWM_KEEP_OFF = 1
DEF_PFACTOR = 100
DEF_IFACTOR = 25
DEF_LED_TEMP_LIMIT = 50                 # LED temp limit: 50 deg C
DEF_BOARD_TEMP_LIMIT = 70               # Board temp limit: 70 deg C
DEF_OCP_AMP = 25                        # Default over current protection value
DEF_OPP_HW_VER_1 = 275                  # Default over power protection value
# registers and addresses
C_REG_TOP_ADC_CH0_A = 0x0004            # Read ADC0 data (12-bit) - current feedback
C_REG_TOP_ADC_CH1_A = 0x0008            # Read ADC0 data (12-bit) - light feedback
C_REG_TOP_ON_OFF_A = 0x000C             # Strangle strobe signal (1-bit)
C_REG_TOP_NFEEDBACK_DELAY_A = 0x0074
LED_CURRENT_FEEDBACK = 0x4
LED_AMPLITUDE_REGISTER = 0x14
LED_TEST_REGISTER = 0x340
LED_TOP_SVMODE_A = 0x40
LED_SV_UPDATE_REGISTER = 0x10
LED_PFACTOR_REGISER = 0x24
LED_IFACTOR_REGISTER = 0x28
LED_OCPVALUE_REGISTER = 0x4C
LED_OPPVALUE_REGISTER = 0x54
LED_PWM_KEEP_OFF_REGISTER = 0x78
LED_BOARD_TEMP_LIMIT_REGISTER = 0x378
LED_LED_TEMP_LIMIT_REGISTER = 0x80
LED_BOARDTEMP_REGISTER = 0x370
LED_LEDTEMP_REGISTER = 0x34
LED_STICKYBITS_REGISTER = 0x358
# sticky error masks
STICKY_BIT_LED_TEMP = 0
STICKY_BIT_BOARD_TEMP = 1
STICKY_BIT_DOOR_SWITCH_OPEN = 3
STICKY_BIT_OCP = 4
# feedback regulation modes
REGULATION_MODES = {
    'light'   : 0x26,
    'current' : 0x24,
    'combined': 0x2E,
    'default' : 4
}


class LED_Exception(Exception):
    def __init__(self, arg):
        self.arg = arg
        super().__init__(arg)


class Visitech_LED_I2C():
    def __init__(self, verbosity=logging.DEBUG):
        """Initialize the i2c bus and set defaults."""
        self.i2c_bus_num = 1
        self.address = LED_I2C_ADDR
        self.i2c_bus = I2C.I2C(self.address, self.i2c_bus_num)
        self.power = None
        self.verbosity = verbosity
        self.logger = None

    def read_register(self, register):
        """Read 4 bytes from the specified register over i2c.

        register (bytes): two byte address of source register
        """

        self.log(logging.DEBUG,
                 'i2c read - reg:{}'.format(hex(register)))
        register = int(register).to_bytes(2, byteorder='big')
        self.i2c_bus.write(register)
        ret = self.i2c_bus.read(4)
        print('read  register {}={} ({})'.format(hexlify(register),
                                                 hexlify(ret),
                                                 int.from_bytes(ret, byteorder='big')))
        return ret

    def write_register(self, register, data):
        """Write data to the specified register over i2c.

        register (bytes): two byte address of destination register
        data (bytes): four bytes to write to register
        """
        self.log(logging.DEBUG,
                 'i2c write - reg:{} val:{}'.format(hex(register), hexlify(data)))
        register = int(register).to_bytes(2, byteorder='big')
        data = int(data).to_bytes(4, byteorder='big')
        print('write register {}={} ({})'.format(hexlify(register),
                                                 hexlify(data),
                                                 int.from_bytes(data, byteorder='big')))
        self.i2c_bus.write(register + data)

    def load_defaults(self):
        """Set all default values on LED driver board."""
        self.write_register(LED_PWM_KEEP_OFF_REGISTER, DEF_PWM_KEEP_OFF)
        self.write_register(LED_PFACTOR_REGISER, DEF_PFACTOR)
        self.write_register(LED_IFACTOR_REGISTER, DEF_IFACTOR)
        self.set_led_temp_limit(DEF_LED_TEMP_LIMIT)
        self.set_board_temp_limit(DEF_BOARD_TEMP_LIMIT)
        self.set_ocp_limit(DEF_OCP_AMP)
        self.write_register(LED_OPPVALUE_REGISTER, DEF_OPP_HW_VER_1)

    def enable(self):
        """Enable light output.

        Turns on the LED driver. When on the LED driver will output
        current to the LED when a trigger pulse is received from the
        TI sequencer.
        """
        self.write_register(C_REG_TOP_ON_OFF_A, 1)

    def disable(self):
        """Disable light output.

        Turns off the LED driver. When off the LED driver will not
        output current to the LED, even when a trigger pulse is
        received.
        """
        self.write_register(C_REG_TOP_ON_OFF_A, 0)

    def get_amplitude(self):
        """Get the current set amplitude value for the LED."""
        return self.read_register(LED_AMPLITUDE_REGISTER)

    def set_amplitude(self, amplitude):
        """Set the amplitude value for the LED.

        Amplitude is an integer between 0 and 2000
        """
        if 0 > amplitude > 2000:
            msg = 'Provided LED amplitude of {} is out of range' .format(amplitude)
            self.log(logging.CRITICAL, msg)
            raise LED_Exception(msg)
        if amplitude > 100:
            msg = 'LED amplitude of {} is higher than recommended maximum of 100'
            self.log(logging.WARN, msg)
        self.write_register(LED_AMPLITUDE_REGISTER, amplitude)
        self.write_register(LED_SV_UPDATE_REGISTER, 1)
        self.write_register(LED_SV_UPDATE_REGISTER, 0)

    def get_sticky_errors(self):
        """Return the current error status as a list.

        Sticky errors are used to indicate that a runtime protection
        was triggered since last reading the errors, such as the LED
        over-current protection. Once the values are read the errors
        are reset, they can however be triggered immediately after
        clearing if the error state is still apparent. The errors are
        reported Multiple errors can be reported at once and are
        returned as a list.

        Available errors:
            -BOARD TEMPERATURE LIMIT EXCEEDED - Board temperature
                protection has been exceeded.
            -LED TEMPERATURE LIMIT EXCEEDED - LED temperature protection
                has been exceeded.
            -LED SAFETY SWITCH OPEN - The safety switch is in
                open-circuit, no light output will be generated.
            -LED OVER CURRENT PROTECTION TRIGGERED - LED over current
                protection has been triggered. Raise OCP value or lower
                the LED amplitude
        """
        sticky_bits = self.read_register(LED_STICKYBITS_REGISTER)
        error_list = []
        if sticky_bits & (1 << STICKY_BIT_BOARD_TEMP):
            error_list.append('BOARD TEMPERATURE LIMIT EXCEEDED')
        if sticky_bits & (1 << STICKY_BIT_LED_TEMP):
            error_list.append('LED TEMPERATURE LIMIT EXCEEDED')
        if sticky_bits & (1 << STICKY_BIT_DOOR_SWITCH_OPEN):
            error_list.append('LED SAFETY SWITCH OPEN')
        if sticky_bits & (1 << STICKY_BIT_OCP):
            error_list.append('LED OVER CURRENT PROTECTION TRIGGERED')
        self.clear_sticky_errors()
        return error_list

    def clear_sticky_errors(self):
        """Clear the current sticky errors by resetting the register."""
        self.write_register(LED_STICKYBITS_REGISTER, 0xff)

    def get_led_temp(self):
        """Return the temperature of the LED in Celsius as a float."""
        temp = self.read_register(LED_LEDTEMP_REGISTER)
        return float(temp) / 10

    def get_board_temp(self):
        """Return the temperature of the LED driver board in Celsius as
        a float.
        """
        temp = self.read_register(LED_BOARDTEMP_REGISTER)
        return float(temp) / 256

    def get_led_temp_limit(self):
        """Return the temperature limit for the LED in Celsius as a
        float.
        """
        return float(self.read_register(LED_LED_TEMP_LIMIT_REGISTER)) / 10

    def get_board_temp_limit(self):
        """Return the temperature limit for the LED driver board in
        Celsius as a float.
        """
        return float(self.read_register(LED_BOARD_TEMP_LIMIT_REGISTER))

    def set_led_temp_limit(self, limit):
        """Set the temperature limit (int) for the LED in Celsius.

        It is not recommended to exceed the default value as this will
        shorten the lifetime of the LED. Once the temperature exceeds
        the temperature limit, the LED is turned off and an error is set
        in the sticky errors.
        """
        self.write_register(LED_LED_TEMP_LIMIT_REGISTER, limit * 10)

    def set_board_temp_limit(self, limit):
        """Set the temperature limit for the LED driver board (int) in
        Celsius.

        It is not recommended to exceed the default value as this will
        shorten the lifetime of the LED. Once the temperature exceeds
        the temperature limit, the LED is turned off and an error is set
        in the sticky errors.
        """
        self.write_register(LED_BOARD_TEMP_LIMIT_REGISTER, limit)

    def get_ocp_limit(self):
        limit = self.read_register(LED_OCPVALUE_REGISTER)
        return float(limit) * OCP_AMP_PER_UNIT_HW_VER1

    def set_ocp_limit(self, limit):
        """Set the LED driver over-current protection value in Amps
        (int).

        It is not recommended to exceed the default value as this will
        shorten the lifetime of the LED.
        """
        self.write_register(LED_OCPVALUE_REGISTER, int(limit / OCP_AMP_PER_UNIT_HW_VER1))

    def get_regulation_mode(self):
        """Return the regulation mode in use for controlling light the
        output from LED.

        Can be 'light', 'current', 'combined' or 'default'.
        """
        mode = self.read_register(LED_TOP_SVMODE_A)
        try:
            mode = next(k for k, v in REGULATION_MODES.items() if v == mode)
        except StopIteration:
            msg = 'Bad mode "{}" read from LED driver'.format(mode)
            self.log(logging.CRITICAL, msg)
            raise LED_Exception(msg)
        return mode

    def set_regulation_mode(self, mode):
        """Set the regulation mode to be used for controlling light
        output from LED.

        Can be 'light', 'current', 'combined' or 'default'. 'light' is
        recommended.

        To be able to readout feedback for both current and light you
        must run it in 'combined' mode. This will regulate using the
        light sensor, but will sample both ADC’s.
        """
        if mode not in REGULATION_MODES:
            msg = 'Bad mode "{}" supplied to LED driver'.format(mode)
            self.log(logging.CRITICAL, msg)
            raise LED_Exception(msg)
        return self.write_register(LED_TOP_SVMODE_A, mode)

    def get_current_feedback(self):
        """Return the current passing through the LED driver on the last
        strobe in Amps as a float.
        """
        if not self.get_running_status():
            return 0
        current = self.read_register(C_REG_TOP_ADC_CH0_A)
        return float(current) / 77.81

    def get_light_feedback(self):
        """Return the recorded light feedback value of the last strobe
        from the light sensors as a float.

        This should correspond to the current amplitude set if no
        protections have been triggered.
        """
        if not self.get_running_status():
            return 0
        return self.read_register(C_REG_TOP_ADC_CH1_A)

    def get_running_status(self):
        """Return the status of the LED driver as a boolean.

        Get the status of the light output. If the LED driver and the
        sequencer are turned on this command will wait for a few msec
        to see if the driver receives a trigger and successfully
        strobes. When True is returned, the LED has been outputting
        light since the command was executed. If LED driver or sequencer
        is off then the command returns immediately with False.

        """
        # if led is not on, it is not running
        if not self.read_register(C_REG_TOP_ON_OFF_A):
            return False
        # if LED amplitude is set to 0, it is not running
        if not self.get_amplitude():
            return False
        # if analog current or light feedback values have changed, it is running
        mode = self.get_regulation_mode()
        curr, prev = None, None
        if mode in (REGULATION_MODES['light'], REGULATION_MODES['combined']):
            prev = self.read_register(C_REG_TOP_ADC_CH1_A)
        elif mode in (REGULATION_MODES['current'], REGULATION_MODES['default']):
            prev = self.read_register(C_REG_TOP_ADC_CH0_A)
        for _ in range(8):
            if mode in (REGULATION_MODES['light'], REGULATION_MODES['combined']):
                curr = self.read_register(C_REG_TOP_ADC_CH1_A)
            elif mode in (REGULATION_MODES['current'], REGULATION_MODES['default']):
                curr = self.read_register(C_REG_TOP_ADC_CH0_A)
            if curr != prev:
                return True
        # if nothing changed in 8 reads, it is not running
        return False

    def get_all_status(self):
        """Return a string representing the current status"""
        return json.dumps({
            'running status': self.get_running_status(),
            'amplitude': self.get_amplitude(),
            'light feedback': self.get_light_feedback(),
            'current feedback': self.get_current_feedback(),
            'regulation mode': self.get_regulation_mode(),
            'board temperature': self.get_board_temp(),
            'led temperature': self.get_led_temp(),
            'ocp limit': self.get_ocp_limit(),
            'board temperature limit': self.get_board_temp_limit(),
            'led temperature limit': self.get_led_temp_limit(),
            'sticky errors': self.get_sticky_errors()
        }, indent=2, sort_keys=True)

    def stress_test_i2c(self, iterations):
        """Repeatedly write and read from the LED aplitude register for
        iterations number of times.
        """
        for j in range(iterations):
            self.log(logging.DEBUG, 'i2c stress test iteration {}'.format(j))
            for i in range(100):
                self.set_amplitude(i)
                amplitude = self.get_amplitude()
                if amplitude != i:
                    raise LED_Exception('I2C stress test failed')

    def log(self, lvl, msg):
        """Log message.

        If no logger is supplied, print the std output.
        """
        try:
            self.logger.log(lvl, msg)
        except AttributeError:
            if lvl >= self.verbosity:
                print(msg)


if __name__ == '__main__':
    led = Visitech_LED_I2C(verbosity=logging.DEBUG)
    print(led.get_all_status())
    led.load_defaults()
    led.set_amplitude(100)
    print(led.get_amplitude())
    led.set_amplitude(50)
    print(led.get_amplitude())
    led.set_amplitude(77)
    print(led.get_amplitude())
    print(led.get_all_status())
    led.stress_test_i2c(10)
