import time
import logging
import threading
from decimal import Decimal
from printer_server.threading_wrapper import Thread
from printer_server.drivers.generic_drivers import USBSerial


def decimal_to_scientific(number, precision):
    scientific_notation = f"{Decimal(number):+.{precision}E}"
    # add leading 0 to exponent
    if scientific_notation[-2] == '+' or scientific_notation[-2] == '-':
        scientific_notation = scientific_notation[:-1] + '0' + scientific_notation[-1:]
    # remove leading +
    if scientific_notation[0] == '+':
        scientific_notation = scientific_notation[1:]
    return scientific_notation

def parse_pressure(log, pressure):
    if "LO<" in pressure:
        return float("-inf")
    elif "ATM" in pressure:
        return float("inf")
    elif "RP_OFF" in pressure:
        log.error(f"HC and CC power is turned OFF from rear panel control")
        return None
    elif "CTRL_OFF" in pressure:
        log.error("CC or HC is OFF in controlled state")
        return None
    elif "PROT_OFF" in pressure:
        log.error("CC or HC is OFF in protected state")
        return None
    elif "OFF" in pressure:
        log.error("Cold cathode HV is OFF, or HC/PR/CP power is OFF.")
        return None
    elif "WAIT" in pressure:
        log.error("CC or HC startup delay")
        return None
    elif "LowEmis" in pressure:
        log.error("HC OFF due to low emission")
        return None
    elif "MISCONN" in pressure:
        log.error("Sensor improperly connected, or broken filament (PR, CP only)")
        return None
    elif "NO_GAUGE" in pressure or "NOGAUGE" in pressure:
        log.error("Controller unable to determine sensor connection.")
        return None
    elif ">1.0E+03" in pressure:
        return float(1000)
    else:
        return float(pressure)

class MKS946(USBSerial):
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__("MKS", vid=config_dict["mks_vendor_id"], pid=config_dict["mks_product_id"], sn=config_dict["mks_serial_number"], baudrate=config_dict["mks_baudrate"], timeout=0.1, logger=self.log)

        self.config_dict = config_dict
        self.address = config_dict["mks_address"]
        self.thread_running = False
        self.pressures = None
        self.thread = Thread(self.log, name="mks_poll_thread", target=self.loop)
        self.sendLock = threading.Lock()
        self.relay_requests = [0,0,0,0,0,0,0,0,0,0,0,0,0]

    def initialize(self):
        if self.connected:
            self.log.info("Setting atm pressure")
            self.set_atmospheric_pressure(1, self.config_dict["atm pressure"])
            self.set_atmospheric_pressure(2, self.config_dict["atm pressure"])
            self.log.info("Setting relays")
            for _, relay in self.config_dict["relays"].items():
                relay_num = relay["relay_num"]
                if relay["mode"] == "auto":
                    self.set_relay_direction(relay_num, relay["direction"])
                    self.set_relay_setpoint(relay_num, relay["setpoint"])
                    self.set_relay_hysteresis(relay_num, relay["hysterisis"])
                    self.set_relay_mode(relay_num, 'ENABLE')
                else:
                    self.set_relay_mode(relay_num, 'CLEAR', force=True)
            self.start_thread()
            self.log.info("MKS initialized")

    def disconnect(self):
        if self.connected:
            self.stop_thread()
            self.log.info("Clearing relays")
            for _, relay in self.config_dict["relays"].items():
                if relay["mode"] != "auto":
                    self.set_relay_mode(relay['relay_num'], 'CLEAR', force=True)
        super().disconnect()

    def start_thread(self):
        if not self.thread_running:
            self.thread_running = True
            self.thread.start()

    def stop_thread(self):
        if self.thread_running:
            self.thread_running = False
            self.thread.join()
            self.thread = Thread(self.log, name="mks_poll_thread", target=self.loop)

    def loop(self):
        from printer_server.drivers.mks.mks_snip import get_gauges, get_relay_status, cranePosition
        while self.thread_running:
            if self.connected:
                get_relay_status(emit=True)
                get_gauges(emit=True)
                cranePosition(emit=True)
            time.sleep(0.1)

    def query(self, command, n=None, parameter=""):
        '''
        @<aaa><Command>?;FF
        The corresponding response is
        @<aaa>ACK<Response>;FF
        Here, <aaa>: Address, 1 to 254
        <Command>: Commands as described in 9.3 to 9.14
        <Response> Responses as described in 9.3 to 9.14
        For example, to query pressure on channel A1, use
        @003PR1?;FF
        and the corresponding response is
        @003ACK7.602E+2;FF
        Here, <aaa>=003; <Command>=PR1; <Response>=7.602E+2
        '''
        with self.sendLock:
            cmd_str = f"@{self.address}{command}"
            if n != None:
                cmd_str += f"{n}"
            cmd_str += f"?"
            if parameter != "":
                cmd_str += f"{parameter}"
            cmd_str += f";FF"

            trys = 3
            for _ in range(trys):
                rsp_str = self.send(cmd_str)

                if (f"@{self.address}ACK" in rsp_str) and (";FF" in rsp_str):
                    rsp_str = rsp_str.replace(f"@{self.address}ACK","")
                    rsp_str = rsp_str.replace(f";FF","")
                    
                    return rsp_str
                
                elif (f"@{self.address}NAK" in rsp_str) and (";FF" in rsp_str):
                    rsp_str = rsp_str.replace(f"@{self.address}NAK","")
                    rsp_str = rsp_str.replace(f";FF","")
                    self.log.error(self.parse_error_code(int(rsp_str)))
                    return None
                
                else:
                    self.log.error("NAK: QUERY RSP FORMAT ERROR (%s) (%s)", cmd_str, rsp_str)
            return None
        

    def set(self, command, n=None, parameter=""):
        '''
        @<aaa><Command>!<parameter>;FF
        The corresponding response is
        @<aaa>ACK<Response>;FF
        Here, <aaa>: address, 1 to 254
        <Command> Commands as described in 9.3 to 9.13
        <Parameter> Parameter as described in 9.3 to 9.13
        <Response> Responses as described in 9.3 to 9.13
        For example, to set new baud rate, use
        @001BR!19200;FF
        and the corresponding response is
        @001ACK19200;FF
        Here, <aaa>=001; <Command>=BR; <Parameter>=19200;
        <Response>=19200
        '''
        with self.sendLock:
            cmd_str = f"@{self.address}{command}"
            if n != None:
                cmd_str += f"{n}"
            cmd_str += f"!"
            if parameter != "":
                cmd_str += f"{parameter}"
            cmd_str += f";FF"

            rsp_str = self.send(cmd_str)

            if (f"@{self.address}ACK" in rsp_str) and (";FF" in rsp_str):
                rsp_str = rsp_str.replace(f"@{self.address}ACK","")
                rsp_str = rsp_str.replace(f";FF","")
                
                if type(parameter) is int:
                    if command == "SST" and rsp_str == "OFF":
                        rsp_str = 0
                    if int(rsp_str) != parameter:
                        self.log.error(f"Set command '{command}' failed (value '{parameter}' != response '{rsp_str}')")
                        return False
                    return True

                elif type(parameter) is str:
                    if rsp_str != parameter:
                        if command == "PT" and parameter in rsp_str:
                            return True
                        else:
                            self.log.error(f"Set command '{command}' failed (value '{parameter}' != response '{rsp_str}')")
                            return False
                    return True

                else:
                    return rsp_str
            
            elif (f"@{self.address}NAK" in rsp_str) and (";FF" in rsp_str):
                rsp_str = rsp_str.replace(f"@{self.address}NAK","")
                rsp_str = rsp_str.replace(f";FF","")
                self.log.error(self.parse_error_code(int(rsp_str)))
                return False
            
            else:
                self.log.error("NAK: SET RSP FORMAT ERROR (%s) (%s)", cmd_str, rsp_str)
                return False
        
        
    def parse_error_code(self, code):
        '''
        When serial commands are used in communicating with 946, an error code will be returned if an invalid
        command or an invalid parameter is sent. The error code can be displayed in either in TXT or CODE
        mode, and can be selected by using @254SEM!TXT;FF or @254SEM!CODE;FF command, respectively.
        '''

        errors = {
            150: "WRONG_GAUGE",
            151: "NO_GAUGE",
            152: "NOT_IONGAUGE",
            153: "NOT_HOTCATHODE",
            154: "NOT_COLDCATHODE",
            155: "NOT_CAPACITANCE_MANOMETER",
            156: "NOT_PIRANI_OR_CTP",
            157: "NOT_PR_OR_CM",
            158: "NOT_MFC",
            159: "NOT_VLV",
            160: "UNRECOGNIZED_MSG",
            161: "SET_CMD_LOCK",
            162: "RLY_DIR_FIX_FOR_ION",
            163: "INVALID_CHANNEL",
            164: "DIFF_CM",
            165: "INVALID_PID_PARAM",
            166: "PID_IN_PROGRESS",
            167: "INVALID_RATIO_PARAM",
            168: "NOT_IN_DEGAS",
            169: "INVALID_ARGUMENT",
            172: "VALUE_OUT_OF_RANGE",
            173: "INVALID_CTRL_CHAN",
            175: "CMD_QUERY_BYTE_INVALID",
            176: "NO_GAS_TYPE",
            177: "NOT_485",
            178: "CAL_DISABLED",
            179: "SET_POINT_NOT_ENABLED",
            181: "COMBINATION_DISABLED",
            182: "INTERNATIONAL_UNIT_ONLY",
            183: "GAS_TYPE_DEFINED",
            191: "NOT_RATIO_MODE",
            195: "CONTROL_SET_POINT_ENABLED",
            199: "PRESSURE_TOO_HIGH_FOR_DEGAS"
        }
        error =  errors.get(code, "UNKNOWN ERROR")
        return f"NAK: {error}"
    

    ##############################################################
    # Pressure Reading Commands
    ##############################################################

    '''PRn'''
    def read_pressure(self, channel):
        if channel < 1 or channel > 6:
            return None
        rsp = self.query("PR", n=channel)
        if rsp is None:
            return rsp
        return parse_pressure(self.log, rsp)
    
    '''PRZ'''
    def read_all_pressures(self):
        rsp = self.query("PRZ")
        if rsp is None:
            return rsp
        # right now we will only care about the first 2 sensors. if we later add more modules, you can change this
        self.pressures = [parse_pressure(self.log, p) for p in rsp.split(" ")[:2]]
        return self.pressures
    
    '''PCn'''
    def read_combination_pressure(self, channel):
        if channel < 1 or channel > 2:
            return None
        rsp = self.query("PC", n=channel)
        if rsp is None:
            return rsp
        return parse_pressure(self.log, rsp)
    

    ##############################################################
    # Relay and Control Setting Commands
    ##############################################################

    '''
    SPm
    Query or set a set point for relay m, response with the
    current setting value.
    If 0 is used as the parameter, the set point will be set as its
    low limit value.
    
    (m=1 to 12)
    Parameter: d.dd E+/-ee (d,e=0 to 9)
    Response: d.dd E+/-ee (d,e=0 to 9)
    '''
    def get_relay_setpoint(self, relay):
        if relay < 1 or relay > 12:
            return None
        rsp = self.query("SP", n=relay)
        if rsp is None:
            return rsp
        return float(rsp)

    def set_relay_setpoint(self, relay, value):
        if relay < 1 or relay > 12:
            return False
        return self.set("SP", n=relay, parameter=decimal_to_scientific(value,2))

    '''
    SHm
    Query or set a hysteresis for relay m, response with the
    current setting value.
    
    (m=1 to 12)
    Parameter: d.dd E+/-ee (d,e=0 to 9)
    Response: d.dd E+/-ee (d,e=0 to 9)
    '''
    def get_relay_hysteresis(self, relay):
        if relay < 1 or relay > 12:
            return None
        rsp = self.query("SH", n=relay)
        if rsp is None:
            return rsp
        return float(rsp)

    def set_relay_hysteresis(self, relay, value):
        if relay < 1 or relay > 12:
            return False
        return self.set("SH", n=relay, parameter=decimal_to_scientific(value,2))

    '''
    SDm
    Query or set the direction for relay m, response with the
    current setting value. For CC and HC, only BELOW can be
    selected.
    NAK: For CC and HC as the relay direction is fixed to BELOW.
    
    (m=1 to 12)
    Parameter: ABOVE, BELOW, or NAK
    Response: ABOVE, BELOW, or NAK
    '''
    def get_relay_direction(self, relay):
        if relay < 1 or relay > 12:
            return None
        rsp = self.query("SD", n=relay)
        return rsp

    def set_relay_direction(self, relay, direction):
        if relay < 1 or relay > 12:
            return False
        if direction != "ABOVE" and direction != "BELOW" and direction != "NAK":
            return False
        return self.set("SD", n=relay, parameter=direction)

    '''
    ENm
    Query or set status for relay m. Response with current
    Enable status. ENABLE enables the relay, its status
    depends on the pressure and set point value, SET forces
    relay activation, regardless of pressure, and CLEAR disable
    relay.
    
    (m=1 to 12)
    Parameter: SET, ENABLE, or CLEAR
    Response: SET, ENABLE, or CLEAR
    '''
    def get_relay_mode(self, relay):
        if relay < 1 or relay > 12:
            return None
        rsp = self.query("EN", n=relay)
        return rsp

    def set_relay_mode(self, relay, state, force=False):
        # self.log.info("Set relay %s to %s", relay, state)
        if relay < 1 or relay > 12:
            return False
        if state != "SET" and state != "ENABLE" and state != "CLEAR":
            return False
        
        if force:
            self.relay_requests[relay] = 0
        if state == "SET":
            self.relay_requests[relay] += 1
        elif state == "CLEAR":
            if self.relay_requests[relay] > 0:
                self.relay_requests[relay] -= 1
        else:
            self.relay_requests[relay] = None
        
        if (state == "SET" and self.relay_requests[relay] == 1) or (state == "CLEAR" and self.relay_requests[relay] == 0) or (state == "ENABLE"):
            return self.set("EN", n=relay, parameter=state)

    '''
    SSm
    Query all the relay setting status, SET is activated, and
    CLEAR is disabled.
    
    (m=1 to 12)
    Response: SET, or CLEAR
    '''
    def get_relay_status(self, relay):
        if relay < 1 or relay > 6:
            return None
        rsp = self.query("SS", n=relay)
        return rsp

    '''
    ENA
    Query single relay set point status (relay1 relay 2 …relay 12).
    0: clear; 1: set; 2: enable.
    
    Response: ddd..ddd (d=0,1,2)
    '''
    def get_all_relay_mode(self):
        rsp = self.query("ENA")
        if rsp is None:
            return rsp
        return list(rsp)

    '''
    SSA
    Query all 12 relay set point status (relay1 relay 2 …relay 12).
    0: clear; 1: set.
    
    Response: ddd..ddd (d=0,1)
    '''
    def get_all_relay_status(self):
        rsp = self.query("SSA")
        if rsp is None:
            return rsp
        return list(rsp)


    ##############################################################
    # Capacitance Manometer Control Commands
    ##############################################################

    # NOT IMPLEMENTED

    ##############################################################
    # Convection Pirani, Convectron and Pirani Control Commands
    ##############################################################
    '''
    ATMn
    Send an atmospheric pressure to perform ATM
    calibration. The PR/CP must be at atmospheric pressure
    when running ATM calibration. Valid range is from 100
    to 1000.
    
    (n=1 to 6)
    Parameter: d.ddE+ee
    Response: d.ddE+ee
    '''
    def get_atmospheric_pressure(self, channel):
        if channel < 1 or channel > 6:
            return None
        rsp = self.query(f"ATM", n=channel)
        if rsp is None:
            return rsp
        return float(rsp)

    def set_atmospheric_pressure(self, channel, pressure):
        if channel < 1 or channel > 6:
            return False
        return self.set("ATM", n=channel, parameter=decimal_to_scientific(pressure, 2))

    '''
    VACn
    Zero a PR/CP on channel n. Execute only when the
    pressure reading is less than 1X10-2 Torr.
    
    (n=1 to 6)
    Response: OK or NAK
    '''
    def zero(self, channel):
        if channel < 1 or channel > 6:
            return False
        return self.set("VAC", n=channel)

    '''
    AZn
    Query or set an autozero (CC or HC) control channel n
    for a PR/CP, or disable autozero (NA). Execute only
    when the pressure reading is less than 1X10-2 Torr.
    
    (n=1 to 6)
    Parameter: A1, B1, A2, B2, C1, C2, or NA
    Response: A1, B1, A2, B2, C1, C2, or NA
    '''
    def get_autozero_ref_channel(self, channel):
        if channel < 1 or channel > 6:
            return None
        rsp = self.query("AZ", n=channel)
        return rsp

    def set_autozero_ref_channel(self, channel, ref_channel):
        if channel < 1 or channel > 6:
            return False
        if (ref_channel != "A1" and ref_channel != "B1" and ref_channel != "A2" and ref_channel != "B2" 
            and ref_channel != "C1" and ref_channel != "C2" and ref_channel != "NA"):
            return False
        return self.set("AZ", n=channel, parameter=ref_channel)

    '''
    GTn
    Query or set a gas type for PR/CP on channel n.
    
    (n=1 to 6)
    Parameter: Nitrogen, Argon, or Helium
    Response: Nitrogen, Argon, or Helium
    '''
    def get_gas_type(self, channel):
        if channel < 1 or channel > 6:
            return None
        rsp = self.query("GT", n=channel)
        return rsp

    def set_gas_type(self, channel, t):
        if channel < 1 or channel > 6:
            return False
        if t != "Nitrogen" and t != "Argon" and t != "Helium":
            return False
        return self.set("GT", n=channel, parameter=t)

    '''
    CPn
    Query the channel power status for PR, CP, HC or high
    voltage status for CC.
    Turn ON/OFF the channel power for PR, CP, HC, or
    high voltage for CC).
    
    (n=1 to 6)
    Parameter: ON or OFF
    Response: ON or OFF
    '''
    def get_power_status(self, channel):
        if channel < 1 or channel > 6:
            return None
        rsp = self.query("CP", n=channel)
        return rsp

    def set_power_status(self, channel, state):
        if channel < 1 or channel > 6:
            return False
        if state != "ON" and state != "OFF":
            return False
        return self.set("CP", n=channel, parameter=state)

    '''
    PTn
    Query or set Pirani sensor type on channel n.
    If Pirani type is set to PR or CP, the PTn command will
    respond PR or CP. If the Pirani is set to AUTO, the PTn
    command will response with the Pirani type it auto
    detects, i.e. AUTO-PR, when it detects the PR.
    
    (n=1 to 6)
    Parameter: AUTO, PR, or CP
    Response: AUTO, PR, CP, AUTO-PR, or AUTO-CP
    '''
    def get_sensor_type(self, channel):
        if channel < 1 or channel > 6:
            return None
        rsp = self.query("PT", n=channel)
        return rsp

    def set_sensor_type(self, channel, t):
        if channel < 1 or channel > 6:
            return False
        if t != "AUTO" and t != "PR" and t != "CP":
            return False
        return self.set("PT", n=channel, parameter=t)

    ##############################################################
    # Cold Cathode Control Commands
    ##############################################################

    # NOT IMPLEMENTED

    ##############################################################
    # Hot Cathode Control Commands
    ##############################################################

    # NOT IMPLEMENTED

    ##############################################################
    # MFC Control Commands
    ##############################################################

    # NOT IMPLEMENTED

    ##############################################################
    # Pressure (Valve) Control Commands
    ##############################################################

    # NOT IMPLEMENTED

    ##############################################################
    # PID Recipe Setting Commands
    ##############################################################

    # NOT IMPLEMENTED

    ##############################################################
    # Ratio Recipe Setting Commands
    ##############################################################

    # NOT IMPLEMENTED

    ##############################################################
    # PID/Ratio Control Activation Command
    ##############################################################

    # NOT IMPLEMENTED

    ##############################################################
    # System Commands
    ##############################################################

    '''
    AD
    Query or set controller address (1 to 253)
    254 is reserved for broadcasting. Default = 253.
    
    Parameter: aaa (aaa=001 to 253)
    Response: aaa (aaa=001 to 253)
    '''
    def get_addr(self):
        rsp = self.query("AD")
        if rsp is None:
            return rsp
        return int(rsp)

    def set_addr(self, addr=253):
        if addr > 253 or addr < 1:
            return False
        return self.set("AD", parameter=addr)

    '''
    BR
    Query or set baud rate
    default = 9600.
    
    Parameter: 9600, 19200, 38400, 57600, or 115200
    Response: 9600, 19200, 38400, 57600, or 115200
    '''
    def get_baud(self):
        rsp = self.query("BR")
        if rsp is None:
            return rsp
        return int(rsp)

    def set_baud(self, baud):
        if baud != 9600 and baud != 19200 and baud != 38400 and baud != 57600 and baud != 115200:
            return False
        return self.set("BR", parameter=baud)

    '''
    PAR
    Query or set the parity for the controller. Default=NONE.
    
    Parameter: NONE, EVEN, or ODD
    Response: NONE, EVEN, or ODD
    '''
    def get_parity(self):
        rsp = self.query("PAR")
        return rsp

    def set_parity(self, parity):
        if parity != "NONE" and parity != "EVEN" and parity != "ODD":
            return False
        return self.set("PAR", parameter=parity)

    '''
    DLY
    485 time delay, t must >= 1 for reliable 485
    communication. Default = 8 msec.
    
    Parameter: t msec
    Response: t msec
    '''
    def get_485_delay(self):
        rsp = self.query("DLY")
        return rsp

    def set_485_delay(self, delay):
        if delay < 1:
            return False
        return self.set("DLY", parameter=delay)

    '''
    U
    Pressure unit
    
    Parameter: Torr, MBAR, PASCAL, or Micron
    Response: Torr, MBAR, PASCAL, or Micron
    '''
    def get_unit(self):
        rsp = self.query("U")
        return rsp

    def set_unit(self, units):
        if units != "Torr" and units != "MBAR" and units != "PASCAL" and units != "Micron":
            return False
        return self.set("U", parameter=units)

    '''
    DM
    Display mode: either standard display, or large font
    display. Default = STD.
    
    Parameter: STD or LRG
    Response: STD or LRG
    '''
    def get_display_mode(self):
        rsp = self.query("DM")
        return rsp


    def set_display_mode(self, mode):
        if mode != "STD" and mode != "LRG":
            return False
        return self.set("DM", parameter= mode)

    '''
    DF
    Display format: either default, patch zero, or high
    resolution (only for HC and CC). Default = Default.
    
    Parameter: Default, PatchZ, or HighR
    Response: Default, PatchZ, or HighR
    '''
    def get_display_format(self):
        rsp = self.query("DF")
        return rsp

    def set_display_format(self, fmt):
        if fmt != "Default" and fmt != "PatchZ" and fmt != "HighR":
            return False
        return self.set("DF", parameter=fmt)

    '''
    LOCK
    Enable (ON) or disable (OFF) front panel lock
    
    Parameter: ON or OFF
    Response: ON or OFF
    '''
    def get_panel_lock(self):
        rsp = self.query("LOCK")
        return rsp

    def set_panel_lock(self, lock):
        if lock != "ON" and lock != "OFF":
            return False
        return self.set("LOCK", parameter=lock)

    '''
    CAL
    Enable or disable User Calibration, default = Enable.
    
    Parameter: Enable or Disable
    Response: Enable or Disable
    '''
    def get_user_calibration_state(self):
        rsp = self.query("CAL")
        return rsp

    def set_user_calibration_state(self, state):
        if state != "Enable" and state != "Disable":
            return False
        return self.set("CAL", parameter=state)

    '''
    SPM
    Enable or disable parameter setting, default = Enable.
    
    Parameter: Enable or Disable
    Response: Enable or Disable
    '''
    def get_parameter_setting_state(self):
        rsp = self.query("SPM")
        return rsp

    def set_parameter_setting_state(self, state):
        if state != "Enable" and state != "Disable":
            return False
        return self.set("SPM", parameter=state)

    '''
    MT
    Display the sensor module type. T1, T2, T3=(CC, HC,
    CM, PR, FC, NC). NC= no connection. T4=(NA, PF, PC)
    
    Response: T1,T2,T3,T4
    '''
    def get_module_types(self):
        rsp = self.query("MT")
        if rsp is None:
            return rsp
        return rsp.split(",")

    '''
    STn
    Display the connected sensor type on the specified
    module (A, B, or C). S1,S2=CC,PR,CP,CM,FC,HC, NG.
    NC=no connection.
    
    (n=A, B, C)
    Response: S1S2
    '''
    def get_sensors_on_module(self, module):
        if module != "A" and module != "B" and module != "C":
            return None
        rsp = self.query("ST", n=module)
        if rsp is None:
            return rsp
        return rsp.split(",")

    '''
    MD
    Type of controller, either 937B, or 946.
    
    Response: 937B or 946
    '''
    def get_controller_type(self):
        rsp = self.query("MD")
        return rsp

    '''
    FDn
    Factory default for sensor module. This will reset the
    user calibration to factory default.
    
    (n=1 to 6)
    Response: OK
    '''
    def reset_module_settings(self, module):
        if module < 1 or module > 6:
            return False
        return self.set("FD", n=module, parameter="OK")

    '''
    FDS
    Factory default for system setup (including address,
    unit, baud rate, recipes, combination, display format,
    screen saver)
    
    Response: OK
    '''
    def reset_controller_settings(self):
        return self.set("FDS")

    '''
    FVn
    Firmware version
    n=1=Slot A; n=2=Slot B; n=3=Slot C
    n=4=AIO; n=5=COMM; n=6=Main
    
    Response: d.dd (d=0 to 9)
    '''
    def get_module_firmware_version(self, module):
        if module < 1 or module > 6:
            return None
        rsp = self.query("FV", n=module)
        return rsp

    '''
    SN
    Display the serial number of the unit.
    
    Response: 10 digit SN
    '''
    def get_controller_serial_number(self):
        rsp = self.query("SN")
        return rsp

    '''
    SNn
    Display the serial number of the card in slot A, B, C, COM,
    Analog and Main
    
    (n=1 to 6)
    Parameter: Read serial number in slot n
    Response: 10 digit SN
    '''
    def get_module_serial_number(self, module):
        if module < 1 or module > 6:
            return None
        rsp = self.query("SN", n=module)
        return rsp

    '''
    SPCn
    Set or query the combination channel setting.
    HH: The channel for HP sensor;
    MM: The channel for MP sensor;
    LL: The channel for LP sensor.
    Valid values for HH, MM, or LL are A1, A2, B1, B2, C1,
    C2, or NA. Default is NA.
    
    (n=1 or 2)
    Parameter: HH,MM,LL
    Response: HH,MM,LL
    '''
    def get_combination_channel_settings(self, channel):
        if channel < 1 or channel > 2:
            return None
        rsp = self.query("SPC", n=channel)
        return rsp.split(",")

    def set_combination_channel_settings(self, channel, H, M, L):
        if channel < 1 or channel > 2:
            return False
        if H != "A1" and H != "B1" and H != "A2" and H != "B2" and H != "C1" and H != "C2" and H != "NA":
            return False
        if M != "A1" and M != "B1" and M != "A2" and M != "B2" and M != "C1" and M != "C2" and M != "NA":
            return False
        if L != "A1" and L != "B1" and L != "A2" and L != "B2" and L != "C1" and L != "C2" and L != "NA":
            return False
        return self.set("SPC", n=channel, parameter=f"{H},{M},{L}")

    '''
    EPCn
    Enable or disable the combination channel. When the
    ombination channel is disabled, the output is 10 V.

    (n=1 or 2)
    Parameter: Enable or Disable
    Response: Enable or Disable
    '''
    def get_combination_sensor_enable(self, channel):
        if channel < 1 or channel > 2:
            return None
        rsp = self.query("EPC", n=channel)
        return rsp

    def set_combination_sensor_enable(self, channel, state):
        if channel < 1 or channel > 2:
            return False
        if state != "Enable" and state != "Disable":
            return False
        return self.set("EPC", n=channel, parameter=state)

    '''
    DLTn
    Query or set the type of DAC linear (LIN, V=A*P) of
    logarithmic linear (LOG, V=A*LogP+B) output. Default
    setting is LOG. (Only LOG is allowed for combined
    output)

    (n=1-6)
    Parameter: LIN or LOG
    Response: LIN or LOG
    '''
    def get_DAC_type(self, channel):
        if channel < 1 or channel > 6:
            return None
        rsp = self.query("DLT", n=channel)
        return rsp

    def set_DAC_type(self, channel, dac_type):
        if channel < 1 or channel > 6:
            return False
        if dac_type != "LIN" and dac_type != "LOG":
            return False
        return self.set("DLT", n=channel, parameter=dac_type)

    '''
    DLAn
    Query or set the DAC slope parameter A. Default value
    is 0.6. Use n=0 for combination output.
    Valid range is from 0.5 to 5 when DLT is set to LOG,
    and 1E-4 to 1E+8 when DLT is set to LIN.

    (n=0-6)
    Parameter: d.dd E+/-ee (d,e=0 to 9)
    Response: d.dd E+/-ee (d,e=0 to 9)
    '''
    def get_DAC_offset_A(self, channel):
        if channel < 0 or channel > 6:
            return None
        rsp = self.query("DLA", n=channel)
        if rsp is None:
            return rsp
        return float(rsp)

    def set_DAC_offset_A(self, channel, value):
        if channel < 0 or channel > 6:
            return False
        return self.set("DLA", n=channel, parameter=decimal_to_scientific(value,2))

    '''
    DLBn
    Query or set the DAC offset parameter B. Default value
    is 7.2. Use n=0 for combination output.
    Valid range is from –20 to 20 when DLT is set to LOG,
    and always equals to zero when DLT is set to LIN.

    (n=0-6)
    Parameter: d.dd E+/-ee (d,e=0 to 9)
    Response: d.dd E+/-ee (d,e=0 to 9)
    '''
    def get_DAC_offset_B(self, channel):
        if channel < 0 or channel > 6:
            return None
        rsp = self.query("DLB", n=channel)
        if rsp is None:
            return rsp
        return float(rsp)

    def set_DAC_offset_B(self, channel, value):
        if channel < 0 or channel > 6:
            return False
        return self.set("DLB", n=channel, parameter=decimal_to_scientific(value,2))

    '''
    IU
    Force the use of international pressure unit (Pascal).

    Parameter: ON or OFF
    Response: ON or OFF
    '''
    def get_force_international_units(self):
        rsp = self.query("IU")
        return rsp

    def set_force_international_units(self, force):
        if force != "ON" and force != "OFF":
            return False
        return self.set("IU", parameter=force)

    '''
    XDL
    Erase the first page of the memory for preparing the
    firmware downloading using Sam-BA after power cycle
    of the controller.
    '''
    def erase_memory(self):
        return self.set("XDL")

    '''
    SEM
    Set the NAK error code response. An error text string is
    returned if it is set to TXT, while an error code is
    returned if it is set to CODE.

    Parameter: TXT or CODE
    Response: TXT or CODE
    '''
    def get_error_code_response(self):
        rsp = self.query("SEM")
        return rsp

    def set_error_code_response(self, mode):
        if mode != "TXT" and mode != "CODE":
            return False
        return self.set("SEM", parameter=mode)


    '''
    SST
    Set and query the screen saver time (in minute) when
    sleep mode (turn OFF front panel display) is activated. 0
    means the screen saver mode is disabled.

    Parameter: 0 to 240
    Response: OFF, 1 to 240
    '''
    def get_screensaver_time(self):
        rsp = self.query("SST")
        if rsp is None:
            return None
        elif rsp == "OFF":
            return 0
        else:
            return int(rsp)

    def set_screensaver_time(self, time):
        if time < 0 or time > 240:
            return False
        return self.set("SST", parameter=time)
    
if __name__ == '__main__':
    config_dict = {
        "dummy": False,
        "mks_hwid": "USB VID:PID=0403:6001 SER=A9AOVRT7",
        "mks_vendor_id": "1027",
        "mks_product_id": "24577",
        "mks_serial_number": "A9AOVRT7",
        "mks_baudrate": 115200,
        "mks_address": "253",
        "teensy_hwid": "PID=16C0:0483 SER=16035730",
        "teensy_vendor_id": "5824",
        "teensy_product_id": "1155",
        "teensy_serial_number": "16035730",
        "teensy_baudrate": 9600,
        "atm pressure": 650,
        "target": [
            0.2,
            0.15
        ],
        "relays": {
            "crane": {
                "relay_num": 1,
                "mode": "auto",
                "direction": "ABOVE",
                "setpoint": 630,
                "hysterisis": 560
            },
            "vacuum_pump": {
                "relay_num": 2,
                "mode": "manual"
            }
        },
        "teensy relays": [
            "valve_vent2",
            "valve_pump2",
            "valve_vacuum",
            "valve_pump1",
            "valve_vent1"
        ]
    }

    mks = MKS946(config_dict=config_dict)
    mks.connect(exit)

    mks.reset_module_settings(0)
    mks.reset_module_settings(1)
    mks.reset_module_settings(2)

    print(f"get_addr: {mks.get_addr()}")
    print(f"get_baud: {mks.get_baud()}")
    print(f"get_parity: {mks.get_parity()}")
    print(f"get_485_delay: {mks.get_485_delay()}")
    print(f"get_unit: {mks.get_unit()}")
    print(f"get_display_mode: {mks.get_display_mode()}")
    print(f"get_display_format: {mks.get_display_format()}")
    print(f"get_panel_lock: {mks.get_panel_lock()}")
    print(f"get_user_calibration_state: {mks.get_user_calibration_state()}")
    print(f"get_parameter_setting_state: {mks.get_parameter_setting_state()}")
    print(f"get_module_types: {mks.get_module_types()}")
    print(f"get_controller_type: {mks.get_controller_type()}")
    print(f"get_controller_serial_number: {mks.get_controller_serial_number()}")
    print(f"get_screensaver_time: {mks.get_screensaver_time()}")

    print(f"get_sensors_on_module A: {mks.get_sensors_on_module('A')}")
    print(f"get_sensors_on_module B: {mks.get_sensors_on_module('B')}")
    print(f"get_sensors_on_module C: {mks.get_sensors_on_module('C')}")

    for i in range(6):
        print(f"get_module_firmware_version {i+1}: {mks.get_module_firmware_version(i+1)}")
        print(f"get_module_serial_number {i+1}: {mks.get_module_serial_number(i+1)}")

    print(f"get_all_relay_mode: {mks.get_all_relay_mode()}")
    print(f"get_all_relay_status: {mks.get_all_relay_status()}")
    for i in range(12):
        print(f"get_relay_setpoint{i+1}: {mks.get_relay_setpoint(i+1)}")
        print(f"get_relay_hysteresis{i+1}: {mks.get_relay_hysteresis(i+1)}")
        print(f"get_relay_direction{i+1}: {mks.get_relay_direction(i+1)}")
        print(f"get_relay_mode{i+1}: {mks.get_relay_mode(i+1)}")
        print(f"get_relay_status{i+1}: {mks.get_relay_status(i+1)}")

    mks.set_atmospheric_pressure(1,650)
    mks.set_atmospheric_pressure(2,650)
    print(f"read_all_pressures: {mks.read_all_pressures()}")
    i=0
    print(f"read_pressure{i+1}: {mks.read_pressure(i+1)}")
    print(f"get_atmospheric_pressure{i+1}: {mks.get_atmospheric_pressure(i+1)}")
    print(f"get_autozero_ref_channel{i+1}: {mks.get_autozero_ref_channel(i+1)}")
    print(f"get_gas_type{i+1}: {mks.get_gas_type(i+1)}")
    print(f"get_power_status{i+1}: {mks.get_power_status(i+1)}")
    print(f"get_sensor_type{i+1}: {mks.get_sensor_type(i+1)}")
    i=1
    print(f"read_pressure{i+1}: {mks.read_pressure(i+1)}")
    print(f"get_atmospheric_pressure{i+1}: {mks.get_atmospheric_pressure(i+1)}")
    print(f"get_autozero_ref_channel{i+1}: {mks.get_autozero_ref_channel(i+1)}")
    print(f"get_gas_type{i+1}: {mks.get_gas_type(i+1)}")
    print(f"get_power_status{i+1}: {mks.get_power_status(i+1)}")
    print(f"get_sensor_type{i+1}: {mks.get_sensor_type(i+1)}")