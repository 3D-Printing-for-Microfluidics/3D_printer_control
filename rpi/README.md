# Setup Raspberry Pi for 3D printer

## Set HDMI output to 2560x1600 @30Hz

Find details here: https://nanomicro.byu.edu:31415/Nordin/5b2d97ab0ce9747020a6e8a4/page

## I2C

    $ sudo raspi-config
    (Turn on I2C)
    $ sudo reboot
    $ sudo apt-get install -y i2c-tools

To install `pigpio`, I used method 3 here, http://abyz.me.uk/rpi/pigpio/download.html.  
The following commands are used. 

    $ rm master.zip
    $ sudo rm -rf pigpio-master
    $ wget https://github.com/joan2937/pigpio/archive/master.zip
    $ unzip master.zip
    $ cd pigpio-master
    $ make
    $ sudo make install

    To start the pigpio daemon
    $ sudo pigpiod
    To stop the pigpio daemon
    $ sudo killall pigpiod

## Autostart 3D printer control software on boot

    $ vim /home/pi/.config/lxsession/LXDE-pi/autostart
    add the following lines
    @sudo pigpiod
    @sudo bash /path/to/3D_printer_control/printer_server/rpi/start.sh