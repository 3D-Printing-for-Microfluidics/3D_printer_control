'''
"Large Stepper Motor"
The purpose of this code is to experiment with running the large stepper motor
This will be built on the script to run the smaller stepper motor
from the documentation, enable must first be turned on for over 50ms(we will use 60ms)
  - Since leaving the enable unwired means it is always enabled, we will only wait 60ms on startup 
and direction setup time must be greater than 5us(we will use 1ms)
'''

import time
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)

# set the input and output pins and give them names
alarm_pin = 18
pulse_pin = 23       # green  (gnd)  yellow (+)
direction_pin = 24   # purple (gnd)  blue   (+)

# set pin directions. Alarm is currently unused 
GPIO.setup(direction_pin,GPIO.OUT)
GPIO.setup(pulse_pin,GPIO.OUT)
GPIO.setup(alarm_pin,GPIO.IN)

# set commonly used delays 
direction_change_delay = .00005   # 50us, must be at least 5us (direction setup time)
pulse_high_time = .00005          # 50us, must be longer than 2.5us (pulse high/low setup time)

# move z axis up by specified number of steps 
def z_up(delay, steps):  # delay is the time between pulses 
    set_direction(1) 
    for i in range(0,steps):
        send_pulse(pulse_high_time, delay)

# move z axis down by specified number of steps 
def z_down(delay, steps): # delay is the time between pulses 
    set_direction(0) 
    for i in range(0,steps):
        send_pulse(pulse_high_time, delay)

# set the motion direction 1=up, 0=down (with sw7 up)
def set_direction(z_direction):    
    GPIO.output(direction_pin, z_direction)
    time.sleep(direction_change_delay)      # this signal needs to be at least 5us ahead of the pulse
                                            # waiting ensures this always happens 

# make a square pulse defined by high and low time 
def send_pulse(time_high, time_low):
    GPIO.output(pulse_pin,1)
    time.sleep(time_high)
    GPIO.output(pulse_pin,0)
    time.sleep(time_low)

try:  
    while True:
        '''

        .5mm vertical translation per revolution 
        Steps per revolution set by switches: 

        -----------------------
        Switch S1  S2  S3  S4 
        -----------------------
        400    On  On  On  On
        800    Off On  On  On
        1600   On  Off On  On
        3200   Off Off On  On
        6400   On  On  Off On
        12800  Off On  Off On
        25600  On  Off Off On
        51200  Off Off Off On
        1000   On  On  On  Off
        2000   Off On  On  Off
        4000   On  Off On  Off
        5000   Off Off On  Off
        8000   On  On  Off Off
        10000  Off On  Off Off
        20000  On  Off Off Off
        40000  Off Off Off Off 

        For accurate operation, the variable steps_per_revolution 
        should agree with the value set by the switches 

        We are using 1600 = On  Off On  On
        
        '''

        distance_per_revolution_mm = .5 # determined by lead screw 
        steps_per_revolution = 1600     # determined by stepper motor switches 

        n_steps = input("How many steps up? ")
        # n_steps = int(int(distance)/1000/distance_per_revolution_mm*steps_per_revolution)
        z_up(pulse_high_time, int(n_steps))

        n_steps = input("How many steps down? ")
        # n_steps = int(int(distance)/1000/distance_per_revolution_mm*steps_per_revolution)
        z_down(pulse_high_time, int(n_steps))

finally:  
    GPIO.cleanup() # this ensures a clean exit even on interrupt 
    print("Clean exit\n")

    


