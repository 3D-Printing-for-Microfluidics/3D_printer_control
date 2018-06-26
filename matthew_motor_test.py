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

#set the input and output pins and give them names
Alarm = 18
Step = 23
Direction = 24
Enable = 25

GPIO.setup(Alarm,GPIO.IN)
GPIO.setup(Step,GPIO.OUT)
GPIO.setup(Direction,GPIO.OUT)
GPIO.setup(Enable,GPIO.OUT)

def upward(delay,steps):
    setStep(0,0,0)
    time.sleep(.060)
    setStep(0,1,0)
    time.sleep(.001)
    for i in range(0,steps):
        setStep(1,1,0)
        time.sleep(delay)
        setStep(0,1,0)
        time.sleep(delay)

def downwards(delay,steps):
    setStep(0,0,0)
    time.sleep(.06)
    setStep(0,0,0)
    time.sleep(.001)
    for i in range(0,steps):
        setStep(1,0,0)
        time.sleep(delay)
        setStep(0,0,0)
        time.sleep(delay)

def setStep(w1,w2,w3):
    GPIO.output(Step,w1)
    GPIO.output(Direction,w2)
    GPIO.output(Enable,w3)







while True:
    delay = .1
    # minimum delay for stepper motor is >5us
    '''
This part of the script assumes that we are operating with the current configuration:
Off On Off Off, this coresponds to 10000 steps per revolution and .5mm vertical
translation per revolution
Steps per revolution can be adjusted by adjusting switches 1-4 on the stepper motor
with the following being example conditions and values
3200 - Off Off On On
6400 - On On Off On
4000 - On Off On Off
10000 - Off On Off Off
40000 - Off Off Off Off
This is controlled with the variable called size, defined below and used in the upward and downwards functions
Also, dpr (distance per revolution) is used to calculate total steps needed based on
inputed displacement
As stated above, the value used is for a microstepping value of 10000 steps per revolution
Note, this script will not work with a step size not evenly divisible by 500 due to the math used
'''
#Vertical Translation Stepper Control
    size = 10000
    dpr = 500
    distance = input("How many um upwards? ")
    upward(delay/1000,int(int(distance)*(size/dpr)))
    distance = input("How many um downwards? ")
    downwards(delay / 1000.0,int(int(distance)*(size/dpr)))
    # This turns off current to the coils so the motor does not get hot(unknown if actually needed)
    # setStep(0, 0, 0)


