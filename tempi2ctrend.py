#!/usr/bin/env python3
# DHT11 -> 16x2 I2C LCD with custom arrow glyphs for trend (↑/↓/→)
import time, collections, logging
from RPLCD.i2c import CharLCD
import Adafruit_DHT

# ---------- CONFIG ----------
LCD_DRIVER='PCF8574'; LCD_ADDR=0x27; I2C_PORT=1; COLS=16
SENSOR = Adafruit_DHT.DHT11
GPIO_PIN = 4
SAMPLE_INTERVAL = 3.0        # seconds between sensor reads
SMOOTH_SAMPLES = 4           # rolling average window for display
TREND_WINDOW = 3             # number of displayed averages to compare
TREND_THRESHOLD = 0.2        # °C to consider meaningful change
DISPLAY_REFRESH = 2.0
LOGFILE = "/tmp/dht11_lcd_trend.log"

# ---------- logging ----------
logging.basicConfig(filename=LOGFILE, level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")

# ---------- LCD init ----------
lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=I2C_PORT, cols=COLS, rows=2)
lcd.backlight_enabled = True

# Create custom glyphs (5x8). Return True if ok.
def setup_custom_chars():
    try:
        # Up arrow
        up =     (0b00100,
                  0b01110,
                  0b10101,
                  0b00100,
                  0b00100,
                  0b00100,
                  0b00100,
                  0b00000)
        # Down arrow
        down =   (0b00100,
                  0b00100,
                  0b00100,
                  0b00100,
                  0b10101,
                  0b01110,
                  0b00100,
                  0b00000)
        # Right arrow (steady)
        right =  (0b00000,
                  0b00100,
                  0b00010,
                  0b11111,
                  0b00010,
                  0b00100,
                  0b00000,
                  0b00000)
        lcd.create_char(0, up)
        lcd.create_char(1, down)
        lcd.create_char(2, right)
        return True
    except Exception as e:
        logging.warning("Custom char setup failed: %s", e)
        return False

CUSTOM_OK = setup_custom_chars()
ARROW_UP   = '\x00' if CUSTOM_OK else '^'
ARROW_DOWN = '\x01' if CUSTOM_OK else 'v'
ARROW_STEADY = '\x02' if CUSTOM_OK else '-'

# ---------- buffers ----------
tbuf = collections.deque(maxlen=SMOOTH_SAMPLES)
hbuf = collections.deque(maxlen=SMOOTH_SAMPLES)
avg_hist = collections.deque(maxlen=TREND_WINDOW)
last_success = False

def ravg(buf): return sum(buf)/len(buf) if buf else None

def compute_trend():
    if len(avg_hist) < 2:
        return ARROW_STEADY
    first = avg_hist[0]; last = avg_hist[-1]
    if last - first > TREND_THRESHOLD:
        return ARROW_UP
    if first - last > TREND_THRESHOLD:
        return ARROW_DOWN
    return ARROW_STEADY

def line1(temp_c):
    if temp_c is None:
        return "T:--.-C  --.-F".ljust(COLS)
    tf = temp_c*9/5 + 32
    s = f"T:{temp_c:4.1f}C {tf:4.1f}F"
    return s[:COLS].ljust(COLS)

def line2(hum, trend_char, ok):
    base = "H:--.-%" if hum is None else f"H:{hum:4.1f}%"
    left = base.ljust(COLS-2)  # reserve last 2 cols: trend + status
    status = "*" if ok else "!"
    return (left + trend_char + status)[:COLS]

def write_lcd(l1, l2):
    try:
        lcd.cursor_pos=(0,0); lcd.write_string(l1)
        lcd.cursor_pos=(1,0); lcd.write_string(l2)
    except Exception as e:
        logging.warning("LCD write retry: %s", e)
        try:
            lcd.clear()
            lcd.cursor_pos=(0,0); lcd.write_string(l1)
            lcd.cursor_pos=(1,0); lcd.write_string(l2)
        except Exception:
            pass

try:
    next_sample = 0.0
    next_refresh = 0.0
    while True:
        now = time.time()

        if now >= next_sample:
            h,t = Adafruit_DHT.read_retry(SENSOR, GPIO_PIN)
            if t is not None and h is not None:
                tbuf.append(float(t)); hbuf.append(float(h))
                last_success = True
                logging.info("OK T=%.1fC H=%.1f%%", t, h)
            else:
                last_success = False
                logging.warning("DHT read failed")
            next_sample = now + SAMPLE_INTERVAL

        if now >= next_refresh:
            tavg = ravg(tbuf)
            havg = ravg(hbuf)
            if tavg is not None:
                avg_hist.append(tavg)
            trend = compute_trend()
            write_lcd(line1(tavg), line2(havg, trend, last_success))
            next_refresh = now + DISPLAY_REFRESH

        time.sleep(0.12)

except KeyboardInterrupt:
    lcd.clear(); lcd.write_string("Stopped".ljust(COLS)); lcd.backlight_enabled=True
except Exception as e:
    logging.exception("Fatal error: %s", e)
    try:
        lcd.clear(); lcd.write_string("Error".ljust(COLS))
    except Exception:
        pass
