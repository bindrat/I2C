#!/usr/bin/env python3
# nifty50_clean.py
# Two-row Nifty50 ticker: price + arrow + percent, no greetings/sensex/weather.
# Blocking refresh: fetches fresh data with yf.download for all symbols.

import time
import datetime
import yfinance as yf
from RPLCD.i2c import CharLCD

# ---------- CONFIG ----------
LCD_DRIVER = 'PCF8574'
LCD_ADDR = 0x27
COLS = 16
ROWS = 2

FETCH_INTERVAL = 120          # seconds between data refreshes
SCROLL_DELAY = 0.30          # seconds per scroll step
UPDATE_SPLASH_SECONDS = 1    # brief "Updating..." splash before fetch

# Nifty50 symbols (Yahoo Finance .NS suffix)
NIFTY50 = [
    "ADANIPORTS.NS","ASIANPAINT.NS","AXISBANK.NS","BAJAJ-AUTO.NS",
    "BAJFINANCE.NS","BAJAJFINSV.NS","BHARTIARTL.NS","BPCL.NS",
    "BRITANNIA.NS","CIPLA.NS","COALINDIA.NS","DIVISLAB.NS",
    "DRREDDY.NS","EICHERMOT.NS","GRASIM.NS","HCLTECH.NS",
    "HDFCBANK.NS","HEROMOTOCO.NS","HINDALCO.NS",
    "HINDUNILVR.NS","ICICIBANK.NS","INDUSINDBK.NS","INFY.NS",
    "ITC.NS","JSWSTEEL.NS","KOTAKBANK.NS","LT.NS",
    "M&M.NS","MARUTI.NS","NESTLEIND.NS","NTPC.NS",
    "ONGC.NS","POWERGRID.NS","RELIANCE.NS","SBILIFE.NS",
    "SBIN.NS","SUNPHARMA.NS","TATACONSUM.NS","TATAMOTORS.NS",
    "TATASTEEL.NS","TCS.NS","TECHM.NS","TITAN.NS",
    "ULTRACEMCO.NS","UPL.NS","WIPRO.NS","ADANIENT.NS",
]

# ---------- LCD init ----------
lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=1, cols=COLS, rows=ROWS)
lcd.backlight_enabled = True

# Custom arrow characters (▲ = \x00, ▼ = \x01)
lcd.create_char(0, (
    0b00100,
    0b01110,
    0b10101,
    0b00100,
    0b00100,
    0b00100,
    0b00100,
    0b00000,
))
lcd.create_char(1, (
    0b00100,
    0b00100,
    0b00100,
    0b00100,
    0b10101,
    0b01110,
    0b00100,
    0b00000,
))

# ---------- State ----------
# symbol -> (price float or None, change float or None, pct float or None)
prices = {s: (None, None, None) for s in NIFTY50}
last_fetch_time = None

# ---------- Helpers ----------
def short_name(sym):
    return sym.replace(".NS", "")

def fetch_prices_blocking(symbols):
    """
    Batch fetch with yf.download for all symbols at once.
    Returns (mapping, error_str_or_None).
    mapping: symbol -> (price, change, pct)
    """
    out = {}
    try:
        data = yf.download(symbols, period="1d", interval="1m", progress=False, auto_adjust=False)
        if data is None or data.empty:
            data = yf.download(symbols, period="5d", interval="1d", progress=False, auto_adjust=False)
            if data is None or data.empty:
                raise RuntimeError("no data returned")

        closes = data['Close']
        if len(closes) >= 2:
            latest = closes.iloc[-1]
            prev = closes.iloc[-2]
        else:
            latest = closes.iloc[-1]
            prev = {}
            for s in symbols:
                try:
                    tk = yf.Ticker(s)
                    prev[s] = tk.info.get('previousClose', None)
                except Exception:
                    prev[s] = None
            import pandas as pd
            prev = pd.Series(prev)

        for s in symbols:
            try:
                lp = float(latest[s])
            except Exception:
                lp = None
            try:
                pv = float(prev[s]) if prev is not None else None
            except Exception:
                pv = None

            if lp is None:
                out[s] = (None, None, None)
            else:
                ch = None if pv is None else (lp - pv)
                pct = None if pv is None else ((lp - pv) / pv * 100.0)
                out[s] = (lp, ch, pct)
        return out, None
    except Exception as e:
        return {s: (None, None, None) for s in symbols}, str(e)

def format_item(name, price, change, pct):
    # compact formatting: PRICE + arrow + percent (percent with 1 decimal)
    if price is None:
        return f"{name}:ERR"
    price_s = f"{price:.0f}" if price >= 100 else f"{price:.2f}"
    arrow = ""
    pct_s = ""
    if change is not None:
        if change > 0:
            arrow = "\x00"
        elif change < 0:
            arrow = "\x01"
    if pct is not None:
        sign = "+" if pct >= 0 else ""
        pct_s = f"{sign}{pct:.1f}%"
    return f"{name}:{price_s}{arrow}{pct_s}"

def build_line(symbols):
    parts = []
    for s in symbols:
        p, ch, pct = prices.get(s, (None, None, None))
        parts.append(format_item(short_name(s), p, ch, pct))
    return " | ".join(parts)

def scroll_two_lines(top_text, bot_text):
    top_s = top_text + "   "
    bot_s = bot_text + "   "
    maxlen = max(len(top_s), len(bot_s))
    for shift in range(maxlen):
        top_window = (top_s + " " * COLS)[shift:shift+COLS]
        bot_window = (bot_s + " " * COLS)[shift:shift+COLS]
        lcd.cursor_pos = (0, 0); lcd.write_string(top_window.ljust(COLS))
        lcd.cursor_pos = (1, 0); lcd.write_string(bot_window.ljust(COLS))
        time.sleep(SCROLL_DELAY)

def show_centered_lines(line1, line2, delay=1):
    lcd.clear()
    lcd.cursor_pos = (0, 0); lcd.write_string(line1.center(COLS))
    lcd.cursor_pos = (1, 0); lcd.write_string(line2.center(COLS))
    time.sleep(delay)

# ---------- Main loop ----------
def main():
    global prices, last_fetch_time
    half = (len(NIFTY50) + 1) // 2
    top_symbols = NIFTY50[:half]
    bot_symbols = NIFTY50[half:]

    # initial fetch
    show_centered_lines("Starting...", "")
    lcd.clear()
    lcd.cursor_pos = (0,0); lcd.write_string("Fetching prices".center(COLS))
    lcd.cursor_pos = (1,0); lcd.write_string("Please wait...".center(COLS))
    new_prices, err = fetch_prices_blocking(NIFTY50)
    if err:
        show_centered_lines("Fetch error", err[:COLS], delay=3)
    else:
        prices.update(new_prices)
        last_fetch_time = datetime.datetime.now()
        show_centered_lines("Updated", last_fetch_time.strftime("%H:%M"), delay=1)

    last_fetch_initiated = time.time()
    try:
        while True:
            # scroll current prices
            top_line = build_line(top_symbols)
            bot_line = build_line(bot_symbols)
            scroll_two_lines(top_line, bot_line)

            # time to refresh?
            if time.time() - last_fetch_initiated >= FETCH_INTERVAL:
                show_centered_lines("Updating...", "", delay=UPDATE_SPLASH_SECONDS)
                # blocking fetch (user OK with waiting)
                lcd.clear()
                lcd.cursor_pos = (0,0); lcd.write_string("Fetching prices".center(COLS))
                lcd.cursor_pos = (1,0); lcd.write_string("Please wait...".center(COLS))
                new_prices, err = fetch_prices_blocking(NIFTY50)
                if err:
                    show_centered_lines("Fetch error", err[:COLS], delay=3)
                else:
                    prices.update(new_prices)
                    last_fetch_time = datetime.datetime.now()
                    show_centered_lines("Updated", last_fetch_time.strftime("%H:%M"), delay=1)
                last_fetch_initiated = time.time()
    except KeyboardInterrupt:
        lcd.clear()
        lcd.write_string("Stopped")
        lcd.backlight_enabled = True

if __name__ == "__main__":
    main()
