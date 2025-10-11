#!/usr/bin/env python3
# i2c_fact.py
# Fetch a random fact and display on 16x2 LCD. Top: FACT, Bottom: scrolling fact.

import time, requests
from RPLCD.i2c import CharLCD

LCD_DRIVER='PCF8574'; LCD_ADDR=0x27; I2C_PORT=1; COLS=16
UPDATE_INTERVAL=90
STATIC_DISPLAY=2.5
SCROLL_STEP=0.15
SCROLL_GAP="    "

FACT_API = "https://uselessfacts.jsph.pl/random.json?language=en"

lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=I2C_PORT, cols=COLS, rows=2)
lcd.backlight_enabled = True

def fetch_fact():
    try:
        r = requests.get(FACT_API, timeout=8)
        r.raise_for_status()
        j = r.json()
        return j.get("text")
    except Exception:
        return None

def scroll_window(full_s, base_time, now_ts):
    if not full_s:
        return "".ljust(COLS)
    if len(full_s) <= COLS:
        return full_s.ljust(COLS)
    static_until = base_time + STATIC_DISPLAY
    if now_ts < static_until:
        return full_s[:COLS].ljust(COLS)
    scroll = full_s + SCROLL_GAP; total = len(scroll)
    elapsed = now_ts - static_until
    step = int(elapsed / SCROLL_STEP)
    pos = step % total
    wrapped = scroll + scroll
    return wrapped[pos:pos+COLS]

def main():
    last_fetch = 0
    fact = None
    base_time = 0
    try:
        while True:
            now = time.time()
            if now - last_fetch >= UPDATE_INTERVAL or fact is None:
                f = fetch_fact()
                if f:
                    fact = f
                    base_time = now
                else:
                    fact = "No fact available."
                    base_time = now
                last_fetch = now

            top = "FACT".center(COLS)
            bottom = scroll_window(fact, base_time, time.time())

            try:
                lcd.cursor_pos=(0,0); lcd.write_string(top)
                lcd.cursor_pos=(1,0); lcd.write_string(bottom)
            except Exception:
                try:
                    lcd.clear()
                    lcd.cursor_pos=(0,0); lcd.write_string(top)
                    lcd.cursor_pos=(1,0); lcd.write_string(bottom)
                except Exception:
                    pass

            time.sleep(0.12)
    except KeyboardInterrupt:
        lcd.clear(); lcd.write_string("Stopped"); lcd.backlight_enabled=True

if __name__=='__main__':
    main()
