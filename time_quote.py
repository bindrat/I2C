#!/usr/bin/env python3
# clock_quotes.py
# Date/time on top row (updates every second).
# Bottom row shows a random quote; long quotes scroll smoothly.
# Ensures each quote remains visible until its full scroll completes.

import time
import random
from datetime import datetime
from RPLCD.i2c import CharLCD

# ---------- CONFIG ----------
LCD_DRIVER = 'PCF8574'
LCD_ADDR = 0x27
COLS = 16
ROWS = 2

QUOTE_INTERVAL = 15        # base seconds between selecting a new short quote
SCROLL_STEP_DELAY = 0.3    # seconds per scroll step for long quotes
LOOP_SLEEP = 0.18          # main loop sleep (controls responsiveness, < SCROLL_STEP_DELAY)
POST_SCROLL_PAUSE = 1.0    # extra pause (seconds) after a full scroll cycle before switching

# ---------- QUOTES ----------
QUOTES = [
    "Keep it simple.",
    "Stay positive.",
    "Focus and win.",
    "Dream big.",
    "Time is precious.",
    "Believe in you.",
    "Work hard.",
    "Never give up.",
    "Think different.",
    "Be curious.",
    "Small steps count.",
    "Patience pays.",
    "Stay humble.",
    "Shine bright.",
    "Push limits.",
    "Chase progress.",
    "One day at a time.",
    "Smile often.",
    "Energy is life.",
    "Courage over fear.",
    "Grow daily.",
    "Trust the process.",
    "Enjoy the ride.",
    "Act with purpose.",
    "Do it now.",
    "Less is more.",
    "Consistency wins.",
    "Adapt & overcome.",
    "Learn & improve.",
    "Balance matters.",
    "Stay grateful.",
    "Progress not perf.",
    "Seek solutions.",
    "Calm is strength.",
    "Clarity is power.",
    "Discipline = freedom",
    "Focus beats luck.",
    "Every day counts.",
    "Risk = reward.",
    "Think long term.",
]

# ---------- LCD init ----------
lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=1, cols=COLS, rows=ROWS)
lcd.backlight_enabled = True

def center_text(s, width):
    s = s[:width]
    return s.center(width)

def left_window(s, start, width):
    # return window of width chars from s starting at start (wrap-around)
    if len(s) <= width:
        return s.ljust(width)
    # create padded scroll string with a gap
    scroll = s + "   "
    wrapped = scroll + scroll  # duplicate so we can slice without modulo each time
    return wrapped[start:start+width]

def choose_quote(prev_quote=None):
    q = random.choice(QUOTES)
    # avoid repeating same quote twice in a row when possible
    if prev_quote and len(QUOTES) > 1:
        tries = 0
        while q == prev_quote and tries < 6:
            q = random.choice(QUOTES)
            tries += 1
    return q

def compute_display_duration(quote):
    """
    For short quotes (<= COLS) return QUOTE_INTERVAL.
    For long quotes, ensure duration covers a full scroll cycle:
      total_scroll_steps = len(quote) + gap (3)
      duration = total_scroll_steps * SCROLL_STEP_DELAY + POST_SCROLL_PAUSE
    Also ensure a minimum of QUOTE_INTERVAL.
    """
    if len(quote) <= COLS:
        return QUOTE_INTERVAL
    total_scroll_len = len(quote) + 3  # quote + gap
    duration = total_scroll_len * SCROLL_STEP_DELAY + POST_SCROLL_PAUSE
    return max(duration, QUOTE_INTERVAL)

def main():
    current_quote = choose_quote()
    quote_selected_time = time.monotonic()
    quote_display_duration = compute_display_duration(current_quote)
    scroll_index = 0
    last_time_sec = -1
    scroll_required = len(current_quote) > COLS
    scroll_last_step = time.monotonic()

    try:
        while True:
            now = datetime.now()
            # Update top row (date + time) once per second
            if now.second != last_time_sec:
                dt_str = now.strftime("%d-%b %H:%M:%S")  # e.g. "02-Oct 17:45:12"
                lcd.cursor_pos = (0, 0)
                lcd.write_string(dt_str.ljust(COLS)[:COLS])
                last_time_sec = now.second

            # Draw bottom row: center if short, scroll if long
            if not scroll_required:
                lcd.cursor_pos = (1, 0)
                lcd.write_string(center_text(current_quote, COLS))
            else:
                # Only advance scroll_index each SCROLL_STEP_DELAY seconds
                if time.monotonic() - scroll_last_step >= SCROLL_STEP_DELAY:
                    scroll_index += 1
                    scroll_last_step = time.monotonic()
                window = left_window(current_quote, scroll_index, COLS)
                lcd.cursor_pos = (1, 0)
                lcd.write_string(window)
                # wrap scroll index to prevent it growing unbounded
                total_scroll_len = len(current_quote) + 3  # quote + gap
                if scroll_index >= total_scroll_len:
                    scroll_index = 0

            # If current quote has been displayed long enough, pick a new one
            if time.monotonic() - quote_selected_time >= quote_display_duration:
                prev = current_quote
                current_quote = choose_quote(prev)
                quote_selected_time = time.monotonic()
                scroll_index = 0
                scroll_required = len(current_quote) > COLS
                scroll_last_step = time.monotonic()
                quote_display_duration = compute_display_duration(current_quote)

            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        lcd.clear()
        lcd.write_string("Stopped")
        lcd.backlight_enabled = True

if __name__ == "__main__":
    main()
