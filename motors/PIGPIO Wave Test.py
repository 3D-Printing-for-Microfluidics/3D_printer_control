'''
Running the motors with the Pi GPIO Library
'''
import pigpio
import time

GPIO = 18

pi = pigpio.pi()

pi.set_mode(GPIO, pigpio.OUTPUT)

pi.set_pull_up_down(GPIO, pigpio.PUD_DOWN)

square=[]

square.append(pigpio.pulse(1<<GPIO, 0,    10))
square.append(pigpio.pulse(0,    1<<GPIO, 20))

# square.append(pigpio.pulse(1<<GPIO, 0,    20))
# square.append(pigpio.pulse(0,    1<<GPIO, 20))

pi.wave_clear()

pi.wave_add_generic(square)
sqr = pi.wave_create()

pi.wave_send_repeat(sqr)

time.sleep(100)

pi.wave_tx_stop()

pi.wave_clear()