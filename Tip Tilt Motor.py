import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

# RPi GPIO pins and corresponding
# ULN2803 board pins
coil_A_1_pin = 18    # IN1
coil_A_2_pin = 23   # IN2
coil_B_1_pin = 24   # IN3
coil_B_2_pin = 25   # IN4

GPIO.setup(coil_A_1_pin, GPIO.OUT)
GPIO.setup(coil_A_2_pin, GPIO.OUT)
GPIO.setup(coil_B_1_pin, GPIO.OUT)
GPIO.setup(coil_B_2_pin, GPIO.OUT)


def forward(delay, steps):  
  for i in range(0, steps):
    setStep(1, 0, 0, 1)
    time.sleep(delay)
    setStep(1, 1, 0, 0)
    time.sleep(delay)
    setStep(0, 1, 1, 0)
    time.sleep(delay)
    setStep(0, 0, 1, 1)
    time.sleep(delay)

def backwards(delay, steps):  
  for i in range(0, steps):
    setStep(1, 0, 0, 1)
    time.sleep(delay)
    setStep(0, 0, 1, 1)
    time.sleep(delay)
    setStep(0, 1, 1, 0)
    time.sleep(delay)
    setStep(1, 1, 0, 0)
    time.sleep(delay)

  
def setStep(w1, w2, w3, w4):
  GPIO.output(coil_A_1_pin, w1)
  GPIO.output(coil_A_2_pin, w2)
  GPIO.output(coil_B_1_pin, w3)
  GPIO.output(coil_B_2_pin, w4)

while True:
  delay = 4
  # First two are for linear translation
  # From spec sheet we know that the motors have 4096 steps per revolution
  size = 4096
  # We also know distance per revolution to be 381 um
  dpr = 381
  # Min delay for 28BYJ-48 is 2 ms, we will set it at 4ms
  distance = input("How many um upwards? ")
  forward(int(delay) / 1000.0, int(int(distance)*(size/dpr)))
  distance = input("How many um downwards? ")
  backwards(int(delay) / 1000.0, int(int(distance)*(size/dpr)))
  # This turns off current to the coils so the motor does not get hot
  setStep(0, 0, 0, 0)

