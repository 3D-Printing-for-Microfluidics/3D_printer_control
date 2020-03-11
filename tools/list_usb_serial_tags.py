import serial
import serial.tools.list_ports

def enumerate_usb_devices():
    x = serial.tools.list_ports.comports()
    print(x)
    for device in x:
        print(device)
        print("\tdevice: '{}'".format(device.device))
        print("\tname: '{}'".format(device.name))
        print("\tdescription: '{}'".format(device.description))
        print("\thwid: '{}'".format(device.hwid))
        print("\tvid: '{}'".format(device.vid))
        print("\tpid: '{}'".format(device.pid))
        print("\tserial_number: '{}'".format(device.serial_number))
        print("\tlocation: '{}'".format(device.location))
        print("\tmanufacturer: '{}'".format(device.manufacturer))
        print("\tproduct: '{}'".format(device.product))
        print("\tinterface: '{}'".format(device.interface))
        if "K-Cube" in device:
            print("Found {}".format(device))
            return device.device
    return None                                # stage not found


if __name__ == "__main__":
    enumerate_usb_devices()
