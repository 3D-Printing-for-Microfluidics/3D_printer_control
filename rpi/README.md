# Autostart 3D printer control software on boot

    $ vim /home/pi/.config/lxsession/LXDE-pi/autostart
    add the following lines
    @sudo pigpiod
    @sudo bash /path/to/3D_printer_control/printer_server/rpi/local_server_start.sh
