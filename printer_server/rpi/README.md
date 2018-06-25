# Setup Raspberry Pi for 3D printer

## Autostart 3D printer control software on boot

    $ vim /home/pi/.config/lxsession/LXDE-pi/autostart
    add line `@sudo bash /path/to/3D_printer_control/printer_server/rpi/start.sh`

## Set HDMI output to 2560x1600 @30Hz

Find details here: https://nanomicro.byu.edu:31415/Nordin/5b2d97ab0ce9747020a6e8a4/page