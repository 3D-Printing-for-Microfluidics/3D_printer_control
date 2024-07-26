import re
import logging
from printer_server.drivers.generic_drivers import USBSerial, TTRStageDriver

# helper function for converting axis name into index
def get_axis_index(axis):
    axis = axis.lower()
    return {"tip": 1, "tilt": 2,}.get(
        axis, 0
    )  # 0 is default if axis is invalid

class TipTilt(USBSerial, TTRStageDriver):
    def __init__(self, config_dict=None, log_level=logging.DEBUG):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)

        super().__init__(vid=config_dict["vendor_id"], pid=config_dict["product_id"], sn=config_dict["serial_number"], logger=self.log)

        self.r = re.compile(r"\d*\.?\d*$")  # regex for getter functions

    # Override USBSerial recive to recieve until 'Done' message
    def receive(self, cmd):
        buffer = b""  # buffer for incoming serial communication
        message = ""  # response to be returned
        error = False  # indicates an error from the
        while True:
            buffer = self.readline()  # wait for the first line to fill in the rx buffer
            while self.in_waiting:  # while there is more data in the rx buffer
                buffer += self.readline()  # read next line from rx buffer
            decoded_buffer = (
                buffer.decode().rstrip().replace("\r\n", " ")
            )  # decode the byte response (as string) without newlines
            message += decoded_buffer  # build response
            if "Error" in message:
                error = True  # indicate error state
            if "Done" in message:
                message = message.replace(" Done", "")  # strip out done message
                if "G" in cmd:
                    message = float(
                        re.findall(self.r, message)[0]
                    )  # parse out values for getter commands
                if error:
                    self.log.warning("There was an error! %s", message)
                return message

    ## wrappers for commands from Teensyduino ##

    # returns "Done"
    def initialize(self):
        return self.send("IN0")

    # returns "Done" or "Error"
    def home(self):
        return self.send("HM0")

    # returns "Done"
    def reset(self):
        return self.send("RS0")

    # returns a float
    def get_position(self, axis):
        position = self.send("GP{}".format(get_axis_index(axis)))
        if position == 12345:
            return "undef"
        else:
            return position

    # returns a float
    def get_min_position(self, axis):
        return self.send("GL{}".format(get_axis_index(axis)))

    # returns a float
    def get_max_position(self, axis):
        return self.send("GU{}".format(get_axis_index(axis)))

    # returns an int
    def get_acceleration(self, axis):
        return self.send("GA{}".format(get_axis_index(axis)))

    # returns "Done"
    def set_acceleration(self, axis, acceleration):
        return self.send("SA{} {}".format(get_axis_index(axis), acceleration))

    # returns an int
    def get_speed(self, axis):
        return self.send("GV{}".format(get_axis_index(axis)))

    # returns "Done"
    def set_speed(self, axis, acceleration):
        return self.send("SV{} {}".format(get_axis_index(axis), acceleration))

    # returns "Done" or "Error"
    def move_relative(self, axis, distance_um, fast=False):
        if fast:  # coarse mode uses less precise positioning for quicker moves
            return self.send("Mr{} {}".format(get_axis_index(axis), distance_um))
        return self.send("MR{} {}".format(get_axis_index(axis), distance_um))

    # returns "Done" or "Error"
    def move_absolute(self, axis, distance_um, fast=False):
        if fast:  # coarse mode uses less precise positioning for quicker moves
            return self.send("Ma{} {}".format(get_axis_index(axis), distance_um))
        return self.send("MA{} {}".format(get_axis_index(axis), distance_um))

    # wrapper to plug into existing calibration threads interface
    def move(self, axis, distance_um, relative=True, fast=False):
        """
        Move the specified number of um at the specified speed (in mm/min)
        """
        if relative:
            self.move_relative(axis, distance_um, fast)
        else:
            self.move_absolute(axis, distance_um, fast)


if __name__ == "__main__":
    t = TipTilt()
    t.connect()
    # t.home()
    print(t.get_position("tip"))
    print(t.get_position("tilt"))
