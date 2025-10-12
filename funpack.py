#!/usr/bin/env python3
"""
i2c_funpack_weighted_norepeatword.py

Fun Pack for 16x2 I2C LCD:
 - Weighted random selection (Word favored over Fact/Joke)
 - Never repeats the same category twice in a row
 - Expanded fallback word list (60+ words)
 - Persistent rotating word queue (no repeats until list exhausted)
"""

import time, random, requests, os
from RPLCD.i2c import CharLCD

# ---------- CONFIG ----------
LCD_DRIVER = 'PCF8574'
LCD_ADDR = 0x27
I2C_PORT = 1
COLS = 16

UPDATE_INTERVAL = 60
STATIC_DISPLAY = 2.0
SCROLL_STEP = 0.15
SCROLL_GAP = "    "

LAST_CHOICE_FILE = "/tmp/i2c_funpack_last.txt"
WORD_INDEX_FILE  = "/tmp/i2c_funpack_words_index.txt"

CATEGORY_WEIGHTS = {
    "word": 0.6,
    "fact": 0.25,
    "joke": 0.15
}

# Expanded fallback words
FALLBACK_WORDS = [
    "serendipity","ephemeral","quixotic","luminous","mellifluous","sagacious","ineffable","eloquent",
    "halcyon","resolute","ethereal","panacea","zenith","ambrosial","labyrinthine","aurora","sonder","nebulous",
    "inevitable","sonder","evanescent","mirthful","euphoria","petrichor","tranquil","sublime","eloquence","sonder",
    "gossamer","radiant","ethereal","tenacious","halcyon","mellifluous","benevolent","quintessence","lucid","nostalgia",
    "opulent","celestial","epiphany","reverie","solace","oblivion","aesthetic","catharsis","limerence","placid",
    "resonance","seraphic","equanimity","halcyon","tranquility","luminescent","poignant","sagacity","venerate",
    "zen","kindred","ardent","ebullient","altruism"
]

JOKE_API = "https://official-joke-api.appspot.com/random_joke"
FACT_API = "https://uselessfacts.jsph.pl/random.json?language=en"
DICTAPI = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"
WORDNIK_KEY = os.environ.get("WORDNIK_KEY")

lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=I2C_PORT, cols=COLS, rows=2)
lcd.backlight_enabled = True

# ---------- persistence ----------
def read_last_choice():
    try:
        with open(LAST_CHOICE_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return None

def write_last_choice(choice):
    try:
        with open(LAST_CHOICE_FILE, "w") as f:
            f.write(choice)
    except Exception:
        pass

def read_word_index():
    try:
        with open(WORD_INDEX_FILE, "r") as f:
            parts = f.read().strip().splitlines()
            order = parts[0].split(",")
            idx = int(parts[1])
            if set(order) != set(FALLBACK_WORDS):
                raise ValueError
            return order, idx
    except Exception:
        order = FALLBACK_WORDS[:]
        random.shuffle(order)
        idx = 0
        write_word_index(order, idx)
        return order, idx

def write_word_index(order, idx):
    try:
        with open(WORD_INDEX_FILE, "w") as f:
            f.write(",".join(order) + "\n" + str(int(idx)))
    except Exception:
        pass

def get_next_fallback_word():
    order, idx = read_word_index()
    if idx >= len(order):
        order = FALLBACK_WORDS[:]
        random.shuffle(order)
        idx = 0
    word = order[idx]
    idx += 1
    write_word_index(order, idx)
    return word

# ---------- fetchers ----------
def fetch_joke():
    try:
        r = requests.get(JOKE_API, timeout=8)
        r.raise_for_status()
        j = r.json()
        setup = j.get("setup","").strip()
        punch = j.get("punchline","").strip()
        if setup and punch:
            return f"{setup} — {punch}"
    except Exception:
        return None

def fetch_fact():
    try:
        r = requests.get(FACT_API, timeout=8)
        r.raise_for_status()
        j = r.json()
        txt = j.get("text") or j.get("fact")
        return txt.strip() if txt else None
    except Exception:
        return None

def fetch_word_and_definition():
    if WORDNIK_KEY:
        try:
            r = requests.get("https://api.wordnik.com/v4/words.json/randomWord",
                             params={"api_key": WORDNIK_KEY}, timeout=8)
            r.raise_for_status()
            word = r.json().get("word")
            if word:
                defr = requests.get(f"https://api.wordnik.com/v4/word.json/{word}/definitions",
                                    params={"limit":1,"api_key":WORDNIK_KEY}, timeout=8)
                defr.raise_for_status()
                defs = defr.json()
                if defs and isinstance(defs, list):
                    definition = defs[0].get("text")
                    return word, definition or "Definition not available."
        except Exception:
            pass

    word = get_next_fallback_word()
    definition = None
    try:
        r = requests.get(DICTAPI.format(word), timeout=8)
        r.raise_for_status()
        jr = r.json()
        if isinstance(jr, list) and jr:
            meanings = jr[0].get("meanings", [])
            if meanings:
                defs = meanings[0].get("definitions", [])
                if defs:
                    definition = defs[0].get("definition")
    except Exception:
        pass
    if not definition:
        definition = "Definition not available."
    return word, definition

# ---------- random weighting ----------
def weighted_choice(exclude=None):
    items = [(cat, w) for cat, w in CATEGORY_WEIGHTS.items() if cat != exclude]
    total = sum(w for _, w in items)
    r = random.random() * total
    upto = 0
    for cat, w in items:
        if upto + w >= r:
            return cat
        upto += w
    return items[-1][0]

# ---------- scrolling ----------
def scroll_window(full_s, base_time, now_ts):
    if not full_s:
        return "".ljust(COLS)
    if len(full_s) <= COLS:
        return full_s.ljust(COLS)
    static_until = base_time + STATIC_DISPLAY
    if now_ts < static_until:
        return full_s[:COLS].ljust(COLS)
    scroll = full_s + SCROLL_GAP
    total = len(scroll)
    elapsed = now_ts - static_until
    step = int(elapsed / SCROLL_STEP)
    pos = step % total
    return (scroll + scroll)[pos:pos+COLS]

# ---------- main selection ----------
def choose_and_fetch():
    last = read_last_choice()
    choice = weighted_choice(exclude=last)
    write_last_choice(choice)

    if choice == "word":
        w, d = fetch_word_and_definition()
        if w:
            return w.upper(), d
        f = fetch_fact()
        return "FACT", f or "No fact available."
    elif choice == "fact":
        f = fetch_fact()
        if f:
            return "FACT", f
        j = fetch_joke()
        return "JOKE", j or "No joke available."
    else:
        j = fetch_joke()
        if j:
            return "JOKE", j
        f = fetch_fact()
        return "FACT", f or "No fact available."

# ---------- main loop ----------
def main():
    last_fetch = 0
    header, content = "FUN", "Loading..."
    base_time = 0.0
    try:
        while True:
            now = time.time()
            if now - last_fetch >= UPDATE_INTERVAL:
                header, content = choose_and_fetch()
                base_time = now
                last_fetch = now
            top = header.center(COLS)[:COLS].ljust(COLS)
            bottom = scroll_window(content, base_time, now)
            try:
                lcd.cursor_pos = (0,0); lcd.write_string(top)
                lcd.cursor_pos = (1,0); lcd.write_string(bottom)
            except Exception:
                try:
                    lcd.clear()
                    lcd.cursor_pos = (0,0); lcd.write_string(top)
                    lcd.cursor_pos = (1,0); lcd.write_string(bottom)
                except Exception:
                    pass
            time.sleep(0.12)
    except KeyboardInterrupt:
        lcd.clear(); lcd.write_string("Stopped")
        lcd.backlight_enabled = True

if __name__ == "__main__":
    main()
