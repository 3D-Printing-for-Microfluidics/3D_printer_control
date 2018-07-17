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
DIRECTION_CHANGE_DELAY_s = .001     # 1ms, must be at least 5us (direction setup time)
HIGH_PULSE_TIME_us = 10              # 10us standard pulse high time 

# set the motion direction 1=up, 0=down (with sw7 off)
def set_z_direction(z_direction):    
    pi.write(DIRECTION_PIN, z_direction)    # set direction to up 
    time.sleep(DIRECTION_CHANGE_DELAY_s)      # this signal needs to be at least 5us ahead of the pulse
                                            # waiting ensures this always happens 

# move z axis by specified number of steps in specified direction
# with specified delay (in microseconds, 50% duty cycle) 
def z_move(direction, steps, delay):
    
    # start_delay = 100
    # min_delay = delay
    # acceleration = 10       # number of steps to accelerate/decelerate through  

    # delay_list = []

    # for i in range(0,steps):
    #     if i < steps/3:
    #         delay_list.append(start_delay-acceleration*i)
    #     elif i < 2*steps/3: 
    #         delay_list.append(min_delay)
    #     else: 
    #         delay_list.append()

    # print("Steps:", steps, "Delays:", len(delay_list))
    # print(*delay_list, sep='\n')
    
    set_z_direction(direction)
    pi.wave_clear()                             # clear the default waveform              
    
    print("Creating pulse list...")
    pulse_list=[]                               # create an empty pulse list 
    # turn on for HIGH_PULSE_TIME_us
    pulse_list.append(pigpio.pulse(1<<PULSE_PIN, 0, HIGH_PULSE_TIME_us))     
    # turn off for delay
    pulse_list.append(pigpio.pulse(0, 1<<PULSE_PIN, delay))      
    
    # print(*pulse_list, sep='\n')
    print("Pulse list done. Steps:", steps, "Pulses:", len(pulse_list))

    print("Adding pulses to waveform...")
    pi.wave_add_generic(pulse_list)             # add the list of pulses to a waveform 
    print("Creating waveform...")
    pulse_waveform_id = pi.wave_create()        # create and save an id for the waveform 
    print("Sending waveform...")
    for i in range(0,steps):                    # for the specified number of steps 
        pi.wave_send_once(pulse_waveform_id)        # send the waveform 
    print("Done.")


def limit_switch_callback(gpio, level, tick):
    if pi.read(LIMIT_PIN):                 # debounce. See if switch is still reading 
        # pi.stop()
        # pi.wave_tx_stop()                   # stop current waveform 
        print("\nPRESS DETECTED", tick, "\n")
    # z_move(1, 32000, 10)



try:

    # initialize connection  
    pi = pigpio.pi()                   

    # set pin directions 
    pi.set_mode(PULSE_PIN, pigpio.OUTPUT)
    pi.set_mode(DIRECTION_PIN, pigpio.OUTPUT)
    pi.set_mode(LIMIT_PIN, pigpio.INPUT)

    # set internal pulldown resistor for limit switch 
    pi.set_pull_up_down(LIMIT_PIN, pigpio.PUD_DOWN)

    ## register callback for limit switch interrupt 
    limit_switch_callback_handle = pi.callback(LIMIT_PIN, pigpio.RISING_EDGE, limit_switch_callback)

    # z_move(0, 5, 20)
    while True: 

        input_direction = input("Direction? 1-up, 0-down ")
        input_steps     = input("How many steps? ")
        input_delay     = input("Delay? (in us, >= 2.5) ")
        
        input_direction = int(input_direction)    
        input_steps = int(input_steps) 
        input_delay = int(input_delay) 

        z_move(input_direction, input_steps, input_delay)
        # z_move(1, 32000, 10)
        # z_move(0, 32000, 10)
        # z_move(1, 32000, 20)
        # z_move(0, 32000, 20)
        # z_move(1, 32000, 30)
        # z_move(0, 32000, 30)
        # z_move(1, 32000, 40)
        # z_move(0, 32000, 40)
        # z_move(1, 32000, 50)



finally:
    pi.wave_tx_stop()
    pi.stop()   # this ensures resources are always cleaned up 

