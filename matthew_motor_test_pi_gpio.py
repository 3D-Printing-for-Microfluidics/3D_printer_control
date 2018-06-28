'''
    Author: Matthew Viglione 
    Date:   6/27/2018 

    Purpose: Run z axis motor with pi gpio Library

    Notes: 

        To use pigpio, you must first start the pigpio daemon with: 

            sudo pigpiod

        For the iES-1706 motor: 
            Direction setup time:      5us 
            High/Low Pulse setup time: 2.5us 
'''

import pigpio
import time

# pin declarations 
PULSE_PIN = 23      # green  (gnd)  yellow (+)
DIRECTION_PIN = 24  # purple (gnd)  blue   (+)
LIMIT_PIN = 18      # limit switch, goes high when pressed 

# important delays 
DIRECTION_CHANGE_DELAY = .001    # 100us, must be at least 5us (direction setup time)

# set the motion direction 1=up, 0=down (with sw7 off)
def set_z_direction(z_direction):    
    pi.write(DIRECTION_PIN, z_direction)    # set direction to up 
    time.sleep(DIRECTION_CHANGE_DELAY)      # this signal needs to be at least 5us ahead of the pulse
                                            # waiting ensures this always happens 

# move z axis by specified number of steps in specified direction
# with specified delay (in microseconds, 50% duty cycle) 
def z_move(direction, steps, delay):
    set_z_direction(direction)
    
    pulse_list=[]  # create an empty pulse list 

    # turn on for delay
    pulse_list.append(pigpio.pulse(1<<PULSE_PIN, 0, delay))
    
    # turn off for delay 
    pulse_list.append(pigpio.pulse(0, 1<<PULSE_PIN, delay))

    # clear the default waveform
    pi.wave_clear()                         

    # add the list of pulses to a waveform 
    pi.wave_add_generic(pulse_list)     

    # create and save an id for the waveform 
    pulse_waveform_id = pi.wave_create()   

    for i in range(0,steps):
        pi.wave_send_once(pulse_waveform_id) # send the waveform 

try:

    # initialize connection
    pi = pigpio.pi()     

    # set pin directions 
    pi.set_mode(PULSE_PIN, pigpio.OUTPUT)
    pi.set_mode(DIRECTION_PIN, pigpio.OUTPUT)
    pi.set_mode(LIMIT_PIN, pigpio.INPUT)

    # pi.set_pull_up_down(PULSE_PIN, pigpio.PUD_DOWN)
    # pi.set_pull_up_down(DIRECTION_PIN, pigpio.PUD_DOWN)

    while True: 

        # input_direction = input("Direction? 1-up, 0-down ")
        # input_steps     = input("How many steps? ")
        # input_delay     = input("Delay? (in us, >= 2.5) ")
        
        # input_direction = int(input_direction)    
        # input_steps = int(input_steps) 
        # input_delay = int(input_delay) 

        # z_move(input_direction, input_steps, input_delay)

        curr_direction = 1; 

        if pi.read(LIMIT_PIN):
            z_move(curr_direction, 32000, 10)
            curr_direction = not curr_direction 




finally:
    pi.stop()   # this ensures resources are always cleaned up 

