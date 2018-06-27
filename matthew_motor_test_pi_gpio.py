'''
Running the motors with pi gpio Library
'''
import pigpio
import time

PULSE_PIN = 18

pi = pigpio.pi()            # initialize connection 



pi.set_mode(PULSE_PIN, pigpio.OUTPUT)

pi.set_pull_up_down(PULSE_PIN, pigpio.PUD_DOWN)

square=[]

square.append(pigpio.pulse(1<<PULSE_PIN, 0,    10))
square.append(pigpio.pulse(0,    1<<PULSE_PIN, 20))

# square.append(pigpio.pulse(1<<PULSE_PIN, 0,    20))
# square.append(pigpio.pulse(0,    1<<PULSE_PIN, 20))

pi.wave_clear()

pi.wave_add_generic(square)
sqr = pi.wave_create()

pi.wave_send_repeat(sqr)

time.sleep(100)

pi.wave_tx_stop()

pi.wave_clear()