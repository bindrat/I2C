#!/usr/bin/env python3
# i2c_word.py
# Word of the day: top shows WORD, bottom scrolls the definition.
# Uses Wordnik if WORDNIK_KEY env is set; otherwise uses a small builtin list + dictionaryapi.dev.

import os, time, random, requests
from RPLCD.i2c import CharLCD

LCD_DRIVER='PCF8574'; LCD_ADDR=0x27; I2C_PORT=1; COLS=16
UPDATE_INTERVAL=6*60*60   # refresh every 6 hours by default when used alone
STATIC_DISPLAY=2.0
SCROLL_STEP=0.2
SCROLL_GAP="    "

lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=I2C_PORT, cols=COLS, rows=2)
lcd.backlight_enabled = True

WORDNIK_KEY = os.environ.get("WORDNIK_KEY")
WORDNIK_RANDOM = "https://api.wordnik.com/v4/words.json/randomWord"
DICTAPI = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"

# small fallback word list (useful if no external API)
FALLBACK_WORDS = [
    "serendipity","ephemeral","quixotic","luminous","mellifluous",
    "sagacious","ineffable","eloquent","halcyon","resolute"
]

def fetch_word_and_definition():
    word = None; definition = None
    if WORDNIK_KEY:
        try:
            r = requests.get(WORDNIK_RANDOM, params={"api_key":WORDNIK_KEY}, timeout=8)
            r.raise_for_status()
            word = r.json().get("word")
            if word:
                # fetch definitions
                defr = requests.get(f"https://api.wordnik.com/v4/word.json/{word}/definitions",
                                    params={"limit":1,"api_key":WORDNIK_KEY}, timeout=8)
                defr.raise_for_status()
                defs = defr.json()
                if defs:
                    definition = defs[0].get("text")
        except Exception:
            word = None; definition = None

    if not word:
        # fallback: choose from list and try dictionaryapi.dev for definition
        word = random.choice(FALLBACK_WORDS)
        try:
            r = requests.get(DICTAPI.format(word), timeout=8)
            r.raise_for_status()
            jr = r.json()
            # dictionaryapi.dev returns a list — find first definition text
            if isinstance(jr, list) and jr:
                meanings = jr[0].get("meanings", [])
                if meanings:
                    defs = meanings[0].get("definitions", [])
                    if defs:
                        definition = defs[0].get("definition")
        except Exception:
            definition = None

    return word, definition or "Definition not available."

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
    word, definition = None, None
    base_time = 0
    try:
        while True:
            now = time.time()
            if now - last_fetch >= UPDATE_INTERVAL or word is None:
                w,d = fetch_word_and_definition()
                if w:
                    word, definition = w, (d or "No definition.")
                    base_time = now
                else:
                    word, definition = "word", "No definition available."
                    base_time = now
                last_fetch = now

            top = (word.upper()[:COLS]).center(COLS)
            bottom = scroll_window(definition, base_time, time.time())

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
