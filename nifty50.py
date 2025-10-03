import time
import yfinance as yf
from RPLCD.i2c import CharLCD

# LCD setup
lcd = CharLCD('PCF8574', 0x27, port=1, cols=16, rows=2)
lcd.backlight_enabled = True

# Nifty 50 tickers (Yahoo Finance symbols with .NS suffix)
NIFTY50 = [
    "ADANIPORTS.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS",
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "BHARTIARTL.NS", "BPCL.NS",
    "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS",
    "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS",
    "HDFC.NS", "HDFCBANK.NS", "HEROMOTOCO.NS", "HINDALCO.NS",
    "HINDUNILVR.NS", "ICICIBANK.NS", "INDUSINDBK.NS", "INFY.NS",
    "ITC.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS",
    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS",
    "SBIN.NS", "SUNPHARMA.NS", "TATACONSUM.NS", "TATAMOTORS.NS",
    "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TITAN.NS",
    "ULTRACEMCO.NS", "UPL.NS", "WIPRO.NS", "ADANIENT.NS",
]

def fetch_prices():
    try:
        data = yf.download(NIFTY50, period="1d", interval="1m")
        last = data['Close'].iloc[-1]
        parts = []
        for symbol in NIFTY50:
            try:
                price = float(last[symbol])
                name = symbol.replace(".NS", "")
                parts.append(f"{name}:{price:.2f}")
            except Exception:
                parts.append(f"{symbol.replace('.NS','')}:ERR")
        return " | ".join(parts)
    except Exception as e:
        return f"Err: {e}"

def scroll_text(text, delay=0.3):
    scroll_str = text + "   "
    for i in range(len(scroll_str) - 15):
        lcd.cursor_pos = (0, 0)
        lcd.write_string(scroll_str[i:i+16])
        time.sleep(delay)

def main():
    try:
        while True:
            msg = fetch_prices()
            print("Ticker:", msg[:100], "...")
            scroll_text(msg)
            time.sleep(2)  # short pause before re-fetch
    except KeyboardInterrupt:
        lcd.clear()
        lcd.write_string("Stopped")
        lcd.backlight_enabled = True

if __name__ == "__main__":
    main()
