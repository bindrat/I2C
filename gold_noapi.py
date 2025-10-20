#!/usr/bin/env python3
"""
gold_silver_fallback.py

Fallback: show Gold/Silver INR per 10g using:
 - Spot metal prices from data-asg.goldprice.org (USD/oz)
 - USD->INR from open.er-api.com (USD base)
 - optional CORRECTION_MULTIPLIER to approximate Indian retail premium
 - cache to /tmp/gold_silver_cache.json

Display: "GOLD10g Rs123456" and "SILV10g Rs123456" (ASCII Rs, no commas)
"""

import time, requests, json, os
from datetime import datetime
from RPLCD.i2c import CharLCD

# ---------- CONFIG ----------
LCD_DRIVER = 'PCF8574'
LCD_ADDR = 0x27
I2C_PORT = 1
COLS = 16

UPDATE_INTERVAL = 300               # seconds between fetches
CORRECTION_MULTIPLIER = 1.08        # multiply spot->INR by this to approximate retail (set to 1.0 to disable)
GOLD_UNIT = '10g'
SILVER_UNIT = '10g'

GOLDPRICE_ENDPOINT = "https://data-asg.goldprice.org/dbXRates/USD"
EXCHANGE_ENDPOINT  = "https://open.er-api.com/v6/latest/USD"
CACHE_FILE = "/tmp/gold_silver_cache.json"

RETRIES = 3
TIMEOUT = 8
TROY_OUNCE_TO_GRAMS = 31.1034768

# ---------- LCD init ----------
lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=I2C_PORT, cols=COLS, rows=2)
lcd.backlight_enabled = True

# ---------- helpers ----------
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

def fetch_spot():
    """Return (xau_usd_per_oz, xag_usd_per_oz) or (None,None)"""
    for _ in range(RETRIES):
        try:
            r = requests.get(GOLDPRICE_ENDPOINT, timeout=TIMEOUT, headers={"User-Agent":"Mozilla/5.0"})
            r.raise_for_status()
            j = r.json()
            items = j.get("items") or []
            if items:
                it = items[0]
                xau = it.get("xauPrice")
                xag = it.get("xagPrice")
                if xau is not None and xag is not None:
                    return float(xau), float(xag)
            # if structure changed, try deep-inspect
            # (we avoid heavy parsing here)
        except Exception:
            time.sleep(1)
    return None, None

def fetch_usd_rates():
    """Return rates dict or None"""
    for _ in range(RETRIES):
        try:
            r = requests.get(EXCHANGE_ENDPOINT, timeout=TIMEOUT)
            r.raise_for_status()
            j = r.json()
            rates = j.get("rates") or j.get("conversion_rates")
            if isinstance(rates, dict):
                return rates
        except Exception:
            time.sleep(1)
    return None

def per_unit_usd(usd_per_ounce, unit):
    if usd_per_ounce is None:
        return None
    usd_per_gram = usd_per_ounce / TROY_OUNCE_TO_GRAMS
    if unit == 'g':
        return usd_per_gram
    if unit == '10g':
        return usd_per_gram * 10.0
    if unit == 'kg':
        return usd_per_gram * 1000.0
    return usd_per_gram

def fmt_int_no_commas(n):
    try:
        return str(int(round(n)))
    except Exception:
        return "ERR"

def build_lines(gold_10g, silver_10g, cached=False):
    def fmt(label, val):
        if val is None:
            s = f"{label}10g RsERR"
        else:
            s = f"{label}10g Rs{fmt_int_no_commas(val)}"
        if len(s) > COLS:
            s = s[:COLS]
        if cached:
            # mark cached with trailing C
            if len(s) >= COLS:
                s = s[:COLS-1] + "C"
            else:
                s = s[:COLS-1] + " " + "C"
        return s.ljust(COLS)
    return fmt("GOLD", gold_10g), fmt("SILV", silver_10g)

# ---------- main ----------
def main():
    cache = load_cache() or {}
    try:
        while True:
            xau_usd, xag_usd = fetch_spot()
            rates = fetch_usd_rates()
            gold_10g = silver_10g = None
            used_cache = False

            if xau_usd is not None and xag_usd is not None and rates:
                inr = rates.get("INR")
                if inr:
                    inr = float(inr)
                    gold_usd = per_unit_usd(xau_usd, GOLD_UNIT)
                    silver_usd = per_unit_usd(xag_usd, SILVER_UNIT)
                    gold_inr = gold_usd * inr * CORRECTION_MULTIPLIER
                    silver_inr = silver_usd * inr * CORRECTION_MULTIPLIER
                    gold_10g = gold_inr
                    silver_10g = silver_inr
                    cache = {"gold_10g": gold_10g, "silver_10g": silver_10g, "updated": datetime.now().isoformat()}
                    save_cache(cache)
            else:
                # fallback to cache if available
                c = load_cache() or cache
                if c:
                    gold_10g = c.get("gold_10g")
                    silver_10g = c.get("silver_10g")
                    used_cache = True

            l1, l2 = build_lines(gold_10g, silver_10g, cached=used_cache)
            try:
                lcd.cursor_pos = (0,0); lcd.write_string(l1)
                lcd.cursor_pos = (1,0); lcd.write_string(l2)
            except Exception:
                try:
                    lcd.clear()
                    lcd.cursor_pos = (0,0); lcd.write_string(l1)
                    lcd.cursor_pos = (1,0); lcd.write_string(l2)
                except Exception:
                    pass

            time.sleep(UPDATE_INTERVAL)
    except KeyboardInterrupt:
        lcd.clear(); lcd.write_string("Stopped".ljust(COLS)); lcd.backlight_enabled = True

if __name__ == "__main__":
    main()
