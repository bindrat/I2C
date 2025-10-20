from gpiozero import LED
from time import sleep

red = LED(17)
green = LED(27)
blue = LED(22)

while True:
    red.on(); green.off(); blue.off()
    print("RED on")
    sleep(1)
    red.off(); green.on(); blue.off()
    print("GREEN on")
    sleep(1)
    red.off(); green.off(); blue.on()
    print("BLUE on")
    sleep(1)
