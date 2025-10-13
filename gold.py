#!/usr/bin/env python3
"""
gold_silver_goldapi.py

Use GoldAPI (needs GOLDAPI_KEY env var) to fetch INR per ounce for XAU/XAG,
convert to INR per 10g, display on 16x2 LCD as 'GOLD10g Rs<val>' and 'SILV10g Rs<val>'.
Retries + cache fallback.
"""

import os, time, requests, json
from datetime import datetime
from RPLCD.i2c import CharLCD

# CONFIG
LCD_DRIVER = 'PCF8574'
LCD_ADDR = 0x27
I2C_PORT = 1
COLS = 16

UPDATE_INTERVAL = 300
CACHE_FILE = "/tmp/gold_silver_cache.json"
RETRIES = 3
TIMEOUT = 8
TROY_OUNCE_TO_GRAMS = 31.1034768

GOLDAPI_BASE = "https://www.goldapi.io/api"
GOLDAPI_KEY = os.environ.get("GOLDAPI_KEY", "").strip()  # must be set

# LCD init
lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=I2C_PORT, cols=COLS, rows=2)
lcd.backlight_enabled = True

# helpers
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

def call_goldapi(symbol):
    """Call GoldAPI endpoint /api/<symbol>/INR and return JSON dict or None."""
    if not GOLDAPI_KEY:
        return None
    url = f"{GOLDAPI_BASE}/{symbol}/INR"
    headers = {"x-access-token": GOLDAPI_KEY}
    for _ in range(RETRIES):
        try:
            r = requests.get(url, headers=headers, timeout=TIMEOUT)
            # if unauthorized or bad key, let caller inspect r.status_code / r.text
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError:
            # if key invalid (401/403) or rate-limited (429), return the response for inspection
            try:
                return r.json()
            except Exception:
                return {"error": f"HTTP {r.status_code}"}
        except Exception:
            time.sleep(1)
    return None

def inr_per_10g_from_goldapi_resp(resp):
    """Given GoldAPI response dict, extract price (INR per ounce) and convert to INR per 10g."""
    if not resp:
        return None
    # GoldAPI typically returns field 'price' = price per ounce in requested currency (INR)
    price = resp.get("price")
    if price is None:
        return None
    try:
        inr_per_ounce = float(price)
        inr_per_gram = inr_per_ounce / TROY_OUNCE_TO_GRAMS
        return inr_per_gram * 10.0
    except Exception:
        return None

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
            if len(s) >= COLS:
                s = s[:COLS-1] + "C"
            else:
                s = (s + " " * (COLS - len(s) - 1))[:COLS-1] + "C"
        return s.ljust(COLS)
    return fmt("GOLD", gold_10g), fmt("SILV", silver_10g)

def main():
    cache = load_cache() or {}
    try:
        while True:
            used_cache = False
            gold_10g = silver_10g = None

            # fetch gold
            gresp = call_goldapi("XAU")
            xau_from_api = inr_per_10g_from_goldapi_resp(gresp) if isinstance(gresp, dict) else None

            # fetch silver
            sresp = call_goldapi("XAG")
            xag_from_api = inr_per_10g_from_goldapi_resp(sresp) if isinstance(sresp, dict) else None

            if xau_from_api is not None or xag_from_api is not None:
                # prefer API values when present
                gold_10g = xau_from_api or cache.get("gold_10g")
                silver_10g = xag_from_api or cache.get("silver_10g")
                cache = {"gold_10g": gold_10g, "silver_10g": silver_10g, "updated": datetime.now().isoformat()}
                save_cache(cache)
            else:
                # fallback to cache
                if cache:
                    gold_10g = cache.get("gold_10g")
                    silver_10g = cache.get("silver_10g")
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
        lcd.clear()
        lcd.write_string("Stopped".ljust(COLS))
        lcd.backlight_enabled = True

if __name__ == "__main__":
    main()
