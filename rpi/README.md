# Autostart 3D printer control software on boot

    $ vim /home/pi/.config/lxsession/LXDE-pi/autostart
    add the following line
    @sudo bash /path/to/3D_printer_control/rpi/local_server_start.sh

# Start printer manually

    Navigate to the 3D_printer_control folder (top level)
    source rpi/local_server_start.sh
