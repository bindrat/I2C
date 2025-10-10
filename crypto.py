#!/usr/bin/env python3
"""
crypto_lcd_btc_scroll_star.py
16x2 LCD crypto ticker:
 - Row 1: BTC scrolling (full price + arrow + percent)
 - Row 2: ETH static (full price + optional arrow/percent if it fits)
 - After each update, a '*' marker is shown at the right end of the ETH line
   for UPDATED_DISPLAY_SECONDS seconds to indicate "fresh update".
"""

import time
import requests
from datetime import datetime
from RPLCD.i2c import CharLCD

# ---------- CONFIG ----------
LCD_DRIVER = 'PCF8574'
LCD_ADDR = 0x27      # change to 0x3F if necessary
I2C_PORT = 1

UPDATE_INTERVAL = 30          # seconds between CoinGecko fetches
COINGECKO_URL = ("https://api.coingecko.com/api/v3/simple/price"
                 "?ids=bitcoin,ethereum&vs_currencies=usd"
                 "&include_24hr_change=true")

# Scrolling params for BTC row
STATIC_DISPLAY = 5.0          # seconds to show leftmost BTC text before scrolling
SCROLL_STEP = 0.5             # seconds per scroll step
SCROLL_GAP = "    "           # gap between repeats when scrolling

# Update marker params
UPDATED_DISPLAY_SECONDS = 3.0  # how long '*' is shown after an update

VERBOSE = False

# ---------- LCD setup ----------
lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=I2C_PORT, cols=16, rows=2)
lcd.backlight_enabled = True

# custom chars for up/down arrows
UP = (
    0b00100,
    0b01110,
    0b11111,
    0b00100,
    0b00100,
    0b00100,
    0b00100,
    0b00000,
)
DOWN = (
    0b00100,
    0b00100,
    0b00100,
    0b00100,
    0b11111,
    0b01110,
    0b00100,
    0b00000,
)
try:
    lcd.create_char(0, UP)
    lcd.create_char(1, DOWN)
except Exception:
    pass

# ---------- helpers ----------
def fetch_prices():
    try:
        r = requests.get(COINGECKO_URL, timeout=10)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, str(e)

def fmt_price_full(num):
    if num is None:
        return "ERR"
    try:
        return f"{int(round(float(num))):,}"
    except Exception:
        return "ERR"

def fmt_change(pct):
    if pct is None:
        return "", ""
    try:
        p = float(pct)
    except Exception:
        return "", ""
    sign = "+" if p >= 0 else ""
    arrow = "\x00" if p >= 0 else "\x01"
    return arrow, f"{sign}{p:.1f}%"

def build_btc_full(price_raw, change_raw):
    price = fmt_price_full(price_raw)
    arrow, pct = fmt_change(change_raw)
    if arrow:
        return f"BTC:{price} {arrow}{pct}"
    return f"BTC:{price}"

def build_eth_line(price_raw, change_raw, show_star=False):
    price = fmt_price_full(price_raw)
    arrow, pct = fmt_change(change_raw)
    base = f"ETH:{price}"
    if arrow:
        candidate = f"{base} {arrow}{pct}"
        if len(candidate) <= 16:
            s = candidate
        else:
            s = base
    else:
        s = base

    # pad/truncate to 16
    s = s[:16].ljust(16)

    # if update marker, replace last char with '*'
    if show_star:
        s = s[:15] + "*"
    return s

def scroll_window(full_s, base_time, now_ts):
    COLS = 16
    if len(full_s) <= COLS:
        return full_s.ljust(COLS)

    static_until = base_time + STATIC_DISPLAY
    if now_ts < static_until:
        return full_s[:COLS].ljust(COLS)

    scroll = full_s + SCROLL_GAP
    total_len = len(scroll)
    elapsed = now_ts - static_until
    step = int(elapsed / SCROLL_STEP)
    pos = step % total_len
    wrapped = scroll + scroll
    return wrapped[pos:pos + COLS]

# ---------- main ----------
def main():
    last_fetch = 0.0
    btc_full_last = ""
    scroll_base_time = 0.0

    btc_price = None
    btc_change = None
    eth_price = None
    eth_change = None

    last_update_time = None

    try:
        while True:
            now = time.time()
            # fetch when due
            if now - last_fetch >= UPDATE_INTERVAL:
                data, err = fetch_prices()
                if err:
                    if VERBOSE:
                        print("Fetch error:", err)
                    lcd.cursor_pos = (0, 0); lcd.write_string("BTC: ERR".ljust(16))
                    lcd.cursor_pos = (1, 0); lcd.write_string("ETH: ERR".ljust(16))
                    last_fetch = now
                    time.sleep(1.0)
                    continue

                btc = data.get("bitcoin", {})
                eth = data.get("ethereum", {})
                btc_price = btc.get("usd")
                btc_change = btc.get("usd_24h_change")
                eth_price = eth.get("usd")
                eth_change = eth.get("usd_24h_change")

                btc_full = build_btc_full(btc_price, btc_change)
                if btc_full != btc_full_last:
                    btc_full_last = btc_full
                    scroll_base_time = now
                    if VERBOSE:
                        print("BTC changed, reset scroll base:", btc_full)

                last_update_time = datetime.now()
                last_fetch = now

            # BTC row (scrolling)
            if btc_price is None:
                btc_display = "BTC: ERR".ljust(16)
            else:
                btc_display = scroll_window(build_btc_full(btc_price, btc_change),
                                            scroll_base_time, time.time())

            # ETH row with update marker
            show_star = False
            if last_update_time:
                elapsed = (datetime.now() - last_update_time).total_seconds()
                if elapsed <= UPDATED_DISPLAY_SECONDS:
                    show_star = True
            eth_display = build_eth_line(eth_price, eth_change, show_star)

            # update LCD
            try:
                lcd.cursor_pos = (0, 0); lcd.write_string(btc_display)
                lcd.cursor_pos = (1, 0); lcd.write_string(eth_display)
            except Exception:
                try:
                    lcd.clear()
                    lcd.cursor_pos = (0, 0); lcd.write_string(btc_display)
                    lcd.cursor_pos = (1, 0); lcd.write_string(eth_display)
                except Exception:
                    pass

            time.sleep(0.12)

    except KeyboardInterrupt:
        lcd.clear()
        lcd.write_string("Stopped")
        lcd.backlight_enabled = True

if __name__ == "__main__":
    main()
