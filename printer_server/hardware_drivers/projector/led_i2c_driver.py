import struct
import logging
from binascii import hexlify
from smbus2 import SMBus

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
regulation_modes = {
    'light'   : 0x26,
    'current' : 0x24,
    'combined': 0x2E,
    'default' : 4
}


class LED_Driver_Exception(Exception):
    def __init__(self, arg):
        self.arg = arg
        super().__init__(arg)


class Visitech_LED_I2C_Driver():

    def __init__(self, verbosity=logging.DEBUG):
        """Initialize the i2c bus and set defaults."""
        self.i2c_bus_num = 1
        self.i2c_bus = SMBus(self.i2c_bus_num)
        self.address = LED_I2C_ADDR
        self.power = None
        self.verbosity = verbosity
        self.logger = None

    def read_led_driver_register(self, register):
        """Read 4 bytes from the specified register over i2c."""
        a = struct.pack('>H', self.address)
        r = struct.pack('>H', register)
        self.log(logging.DEBUG, 'i2c read addr:{} reg:{}'.format(hexlify(a), hexlify(r)))
        return self.i2c_bus.read_i2c_block_data(a, r, 4)

    def write_led_driver_register(self, register, data):
        """Write data to the specified register over i2c."""
        a = struct.pack('>H', self.address)
        r = struct.pack('>H', register)
        d = struct.pack('>I', int(data))
        self.log(logging.DEBUG,
                 'i2c write addr:{} reg:{} val:{}'.format(hexlify(a), hexlify(r), hexlify(d)))
        self.i2c_bus.write_i2c_block_data(a, r, d)

    def load_defaults(self):
        """Set all default values on LED driver board."""
        self.write_led_driver_register(LED_PWM_KEEP_OFF_REGISTER, DEF_PWM_KEEP_OFF)
        self.write_led_driver_register(LED_PFACTOR_REGISER, DEF_PFACTOR)
        self.write_led_driver_register(LED_IFACTOR_REGISTER, DEF_IFACTOR)
        self.set_led_temp_limit(DEF_LED_TEMP_LIMIT)
        self.set_board_temp_limit(DEF_BOARD_TEMP_LIMIT)
        self.set_ocp_limit(DEF_OCP_AMP)
        self.write_led_driver_register(LED_OPPVALUE_REGISTER, DEF_OPP_HW_VER_1)

    def enable(self):
        """Enable light output.

        Turns on the LED driver. When on the LED driver will output
        current to the LED when a trigger pulse is received from the
        TI sequencer.
        """
        self.write_led_driver_register(C_REG_TOP_ON_OFF_A, 1)

    def disable(self):
        """Disable light output.

        Turns off the LED driver. When off the LED driver will not
        output current to the LED, even when a trigger pulse is
        received.
        """
        self.write_led_driver_register(C_REG_TOP_ON_OFF_A, 0)

    def get_amplitude(self):
        """Get the current set amplitude value for the LED."""
        return self.read_led_driver_register(LED_AMPLITUDE_REGISTER)

    def set_amplitude(self, amplitude):
        """Set the amplitude value for the LED.

        amplitude - (int) between 0 and 2000
        """
        if 0 > amplitude > 2000:
            msg = 'Provided LED amplitude of {} is out of range' .format(amplitude)
            self.log(logging.CRITICAL, msg)
            raise LED_Driver_Exception(msg)
        if amplitude > 100:
            msg = 'LED amplitude of {} is higher than recommended maximum of 100'
            self.log(logging.WARN, msg)
        self.write_led_driver_register(LED_AMPLITUDE_REGISTER, amplitude)
        self.write_led_driver_register(LED_SV_UPDATE_REGISTER, 1)
        self.write_led_driver_register(LED_SV_UPDATE_REGISTER, 0)

    def get_sticky_errors(self):
        """Return current error status.

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
        sticky_bits = self.read_led_driver_register(LED_STICKYBITS_REGISTER)
        error_list = []
        if sticky_bits & (1 << STICKY_BIT_BOARD_TEMP):
            error_list.append('BOARD TEMPERATURE LIMIT EXCEEDED')
        if sticky_bits & (1 << STICKY_BIT_LED_TEMP):
            error_list.append('LED  TEMPERATURE LIMIT EXCEEDED')
        if sticky_bits & (1 << STICKY_BIT_DOOR_SWITCH_OPEN):
            error_list.append('LED SAFETY SWITCH OPEN')
        if sticky_bits & (1 << STICKY_BIT_OCP):
            error_list.append('LED OVER CURRENT PROTECTION TRIGGERED')
        self.clear_sticky_errors()
        return error_list

    def clear_sticky_errors(self):
        """Clear the current sticky errors by resetting the register."""
        self.write_led_driver_register(LED_STICKYBITS_REGISTER, 0xff)

    def get_led_temp(self):
        temp = self.read_led_driver_register(LED_LEDTEMP_REGISTER)
        return float(temp) / 10

    def get_board_temp(self):
        temp = self.read_led_driver_register(LED_BOARDTEMP_REGISTER)
        return float(temp) / 256

    def get_led_temp_limit(self):
        return self.read_led_driver_register(LED_LED_TEMP_LIMIT_REGISTER) / 10

    def get_board_temp_limit(self):
        return self.read_led_driver_register(LED_BOARD_TEMP_LIMIT_REGISTER)

    def set_led_temp_limit(self, limit):
        self.write_led_driver_register(LED_LED_TEMP_LIMIT_REGISTER, limit * 10)

    def set_board_temp_limit(self, limit):
        self.write_led_driver_register(LED_BOARD_TEMP_LIMIT_REGISTER, limit)

    def get_ocp_limit(self):
        limit = self.read_led_driver_register(LED_OCPVALUE_REGISTER)
        return float(limit) * OCP_AMP_PER_UNIT_HW_VER1

    def set_ocp_limit(self, limit):
        self.write_led_driver_register(LED_OCPVALUE_REGISTER, limit / OCP_AMP_PER_UNIT_HW_VER1)

    def get_regulation_mode(self):
        mode = self.read_led_driver_register(LED_TOP_SVMODE_A)
        try:
            mode = next(k for k, v in regulation_modes.items() if v == mode)
        except StopIteration:
            msg = 'Bad mode "{}" read from LED driver'.format(mode)
            self.log(logging.CRITICAL, msg)
            raise LED_Driver_Exception(msg)
        return mode

    def set_regulation_mode(self, mode):
        if mode not in regulation_modes:
            raise LED_Driver_Exception('Bad mode "{}"'.format(mode))
        # available modes are set in the defines above
        return self.write_led_driver_register(LED_TOP_SVMODE_A, mode)

    def get_current_feedback(self):
        running = self.get_running_status()
        if not running:
            feedback = 0
        else:
            codes = self.read_led_driver_register(C_REG_TOP_ADC_CH0_A)
            feedback = codes / 77.81
        return feedback

    def get_light_feedback(self):
        if not self.get_running_status():
            return 0
        return self.read_led_driver_register(C_REG_TOP_ADC_CH1_A)

    def get_running_status(self):
        # if led is not on, it is not running
        if not self.read_led_driver_register(C_REG_TOP_ON_OFF_A):
            return 0
        # if LED amplitude is set to 0, it is not running
        if not self.get_amplitude():
            return 0
        # if analog current or light feedback values have changed, it is running
        mode = self.get_regulation_mode()
        curr, prev = None, None
        if mode in (regulation_modes['light'], regulation_modes['combined']):
            prev = self.read_led_driver_register(C_REG_TOP_ADC_CH1_A)
        elif mode in (regulation_modes['current'], regulation_modes['default']):
            prev = self.read_led_driver_register(C_REG_TOP_ADC_CH0_A)
        for _ in range(8):
            if mode in (regulation_modes['light'], regulation_modes['combined']):
                curr = self.read_led_driver_register(C_REG_TOP_ADC_CH1_A)
            elif mode in (regulation_modes['current'], regulation_modes['default']):
                curr = self.read_led_driver_register(C_REG_TOP_ADC_CH0_A)
            if curr != prev:
                return 1
        # if nothing changed in 8 reads, it is not running
        return 0

    def stress_test_i2c(self, iterations):
        for _ in range(iterations):
            for i in range(100):
                self.set_amplitude(i)
                amplitude = self.get_amplitude()
                if amplitude != i:
                    raise LED_Driver_Exception('I2C stress test failed')

    def log(self, lvl, msg):
        try:
            self.logger.log(lvl, msg)
        except AttributeError:
            if lvl > self.verbosity:
                print(msg)


if __name__ == '__main__':
    led = Visitech_LED_I2C_Driver()
    led.load_defaults()
    led.set_amplitude(100)
    # print(led.get_amplitude())
    # led.stress_test_i2c(1)
