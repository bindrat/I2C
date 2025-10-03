# bse_nifty_ticker.py
import time
import datetime
import yfinance as yf
from RPLCD.i2c import CharLCD

# LCD setup - adjust address/driver if needed
LCD_DRIVER = 'PCF8574'
LCD_ADDR = 0x27
lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=1, cols=16, rows=2)
lcd.backlight_enabled = True

# Tickers used by yfinance
SENSEX_SYMBOL = "^BSESN"
NIFTY_SYMBOL = "^NSEI"

def fetch_price_and_change(symbol):
    """
    Use yfinance history to get the latest price and change vs previous close.
    Returns (price (float), change (float)) or (None, None) on failure.
    """
    try:
        tk = yf.Ticker(symbol)
        # Get intraday recent prices; many indices update intraday so 1m interval is OK
        hist = tk.history(period="2d", interval="1m", prepost=False)
        if hist is None or hist.empty:
            # fallback: try daily resolution (last 5 days)
            hist = tk.history(period="5d", interval="1d")
            if hist is None or hist.empty:
                return None, None

        # Latest close price (last available)
        latest_price = float(hist['Close'].iloc[-1])
        # previous close: try previous row, else use info
        if len(hist['Close']) >= 2:
            prev = float(hist['Close'].iloc[-2])
        else:
            info = tk.info
            prev = info.get('previousClose') or latest_price

        change = latest_price - prev
        return latest_price, change
    except Exception as e:
        # don't crash; return None to let main loop display error
        print(f"fetch error for {symbol}: {e}")
        return None, None

def format_line(name, price, change):
    if price is None:
        return f"{name} ERR"
    sign = "+" if change >= 0 else ""
    # shorten price to two decimals and include thousands separator optionally
    try:
        sprice = f"{price:,.2f}"
        schild = f"({sign}{change:,.2f})"
    except:
        sprice = str(price)
        schild = f"({sign}{change})"
    return f"{name} {sprice} {schild}"

def scroll_line(line_text, row=0, delay=0.35):
    """Scroll a single line (row 0 or 1) across the LCD if longer than 16 chars."""
    lcd.cursor_pos = (row, 0)
    if len(line_text) <= 16:
        lcd.write_string(line_text.ljust(16))
        return
    # Add spacing to create gap when scrolling repeats
    scroll_text = line_text + "   "
    for i in range(0, len(scroll_text) - 15):
        lcd.cursor_pos = (row, 0)
        lcd.write_string(scroll_text[i:i+16])
        time.sleep(delay)

def main_loop():
    # We will fetch every 60 seconds (adjust as needed). Between fetches we scroll.
    FETCH_INTERVAL = 60
    last_fetch = 0
    sensex_text = "SENSEX N/A"
    nifty_text = "NIFTY N/A"

    try:
        while True:
            now = time.time()
            if now - last_fetch > FETCH_INTERVAL:
                # fetch fresh values
                sx_price, sx_change = fetch_price_and_change(SENSEX_SYMBOL)
                nf_price, nf_change = fetch_price_and_change(NIFTY_SYMBOL)

                sensex_text = format_line("SENSEX", sx_price, sx_change) if sx_price is not None else "SENSEX ERR"
                nifty_text  = format_line("NIFTY", nf_price, nf_change)   if nf_price is not None else "NIFTY ERR"

                # include timestamp on console for debugging
                print(f"[{datetime.datetime.now().isoformat()}] {sensex_text} | {nifty_text}")
                last_fetch = now

            # Scroll both lines in small steps. This inner loop provides smoother animation between fetches.
            # We will iterate a bit and then check if it's time to fetch again.
            # Build a combined scroll length = max len of lines + gap
            maxlen = max(len(sensex_text), len(nifty_text)) + 3
            for shift in range(maxlen):
                # show window for the top line
                top_window = (sensex_text + "   ")[shift:shift+16] if len(sensex_text) > 16 else sensex_text.ljust(16)
                bot_window = (nifty_text  + "   ")[shift:shift+16] if len(nifty_text)  > 16 else nifty_text.ljust(16)
                lcd.cursor_pos = (0, 0); lcd.write_string(top_window)
                lcd.cursor_pos = (1, 0); lcd.write_string(bot_window)
                time.sleep(0.25)

                # break early if it's time to fetch new data
                if time.time() - last_fetch > FETCH_INTERVAL:
                    break

    except KeyboardInterrupt:
        lcd.clear()
        lcd.write_string("Ticker stopped")
        lcd.backlight_enabled = True
        print("Stopped by user")

if __name__ == "__main__":
    main_loop()
