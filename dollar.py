#!/usr/bin/env python3
"""
currency_lcd_fixed2.py
Show 1 USD -> INR and 1 AED -> INR using open.er-api.com (USD base).
AED->INR computed as INR_per_USD / AED_per_USD.
Retries + cache fallback.
"""

import time, requests, json, os
from datetime import datetime
from RPLCD.i2c import CharLCD

LCD_DRIVER='PCF8574'; LCD_ADDR=0x27; I2C_PORT=1; COLS=16
UPDATE_INTERVAL = 300
EXCHANGE_ENDPOINT = "https://open.er-api.com/v6/latest/USD"
CACHE_FILE = "/tmp/currency_cache.json"
RETRIES = 3; TIMEOUT = 8

lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=I2C_PORT, cols=COLS, rows=2)
lcd.backlight_enabled = True

def save_cache(d):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(d, f)
    except Exception:
        pass

def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None

def fetch_rates():
    for _ in range(RETRIES):
        try:
            r = requests.get(EXCHANGE_ENDPOINT, timeout=TIMEOUT)
            r.raise_for_status()
            j = r.json()
            rates = j.get("rates") or j.get("conversion_rates") or None
            if isinstance(rates, dict):
                return rates
        except Exception:
            time.sleep(1)
    return None

def fmt_money(x):
    if x is None:
        return "ERR"
    try:
        if abs(x - round(x)) < 0.005:
            return f"{int(round(x)):,}"
        return f"{x:,.2f}"
    except Exception:
        return "ERR"

def build_line(label, val, cached=False):
    if val is None:
        s = f"1 {label} = ERR"
        return s[:COLS].ljust(COLS)
    money = fmt_money(val)
    s = f"1 {label} = ₹{money}"
    if cached:
        # indicate cached by a trailing C (or overwrite last char)
        if len(s) >= COLS:
            s = s[:COLS-1] + "C"
        else:
            s = s[:COLS-1] + " " + "C"
    return s[:COLS].ljust(COLS)

def main():
    cache = load_cache() or {}
    try:
        while True:
            rates = fetch_rates()
            used_cache = False
            usd_inr = aed_inr = None
            if rates:
                inr_per_usd = rates.get("INR")
                usd_per_aed = rates.get("AED")  # 1 USD = X AED
                # compute 1 AED = INR as INR_per_USD / AED_per_USD
                if inr_per_usd is not None:
                    usd_inr = float(inr_per_usd)
                    if usd_per_aed is not None and float(usd_per_aed) != 0:
                        aed_inr = float(inr_per_usd) / float(usd_per_aed)
                # save cache if both present
                cache = {"usd_inr": usd_inr, "aed_inr": aed_inr, "updated": datetime.now().isoformat()}
                save_cache(cache)
            else:
                if cache:
                    usd_inr = cache.get("usd_inr")
                    aed_inr = cache.get("aed_inr")
                    used_cache = True

            line1 = build_line("USD", usd_inr, cached=used_cache)
            line2 = build_line("AED", aed_inr, cached=used_cache)

            try:
                lcd.cursor_pos=(0,0); lcd.write_string(line1)
                lcd.cursor_pos=(1,0); lcd.write_string(line2)
            except Exception:
                try:
                    lcd.clear()
                    lcd.cursor_pos=(0,0); lcd.write_string(line1)
                    lcd.cursor_pos=(1,0); lcd.write_string(line2)
                except Exception:
                    pass

            time.sleep(UPDATE_INTERVAL)
    except KeyboardInterrupt:
        lcd.clear(); lcd.write_string("Stopped".ljust(COLS)); lcd.backlight_enabled=True

if __name__ == "__main__":
    main()
