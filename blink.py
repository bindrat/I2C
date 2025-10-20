#!/usr/bin/env python3
"""
led_blink17.py
Simple LED blink script for Raspberry Pi GPIO17
Use between other scripts in the rotator.
"""

from gpiozero import LED
from time import sleep

led = LED(17)  # GPIO17 = pin 11
led.on()
sleep(0.5)     # LED ON for 0.2 sec
led.off()
