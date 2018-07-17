import pigpio
import time

OUPUT_PIN = 23      
HIGH_PULSE_TIME_us = 10                 # 10us pulse high time 

pi = pigpio.pi()                        # initialize connection 
pi.set_mode(OUPUT_PIN, pigpio.OUTPUT)   # set pin direction
pi.wave_clear()                         # clear the waveform buffer             

periods = input("How many periods? ")   # prompt for number of periods 

print("Creating pulse list...")
pulse_list=[]                               # create an empty pulse list 

for i in range(0,int(periods)):             # for the specified number of periods 
    # turn OUPUT_PIN on for HIGH_PULSE_TIME_us
    pulse_list.append(pigpio.pulse(1<<OUPUT_PIN, 0, HIGH_PULSE_TIME_us))     
    # turn OUPUT_PIN off for some delay
    pulse_list.append(pigpio.pulse(0, 1<<OUPUT_PIN, 10))      

print("Pulse list done. Pulses:", len(pulse_list))

print("Adding pulses to waveform...")
pi.wave_add_generic(pulse_list)             # add the list of pulses to a waveform

print("Creating waveform...")
pulse_waveform_id = pi.wave_create()        # create and save an id for the waveform 

print("Sending waveform...")
pi.wave_send_once(pulse_waveform_id)        # send the waveform 

print("Done.")