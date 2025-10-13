#!/usr/bin/env python3
"""
i2c_word_improved_longlist.py

Word-of-the-Day for 16x2 I2C LCD
--------------------------------
✓ Fetches from Wordnik (if WORDNIK_KEY present) or Random Word API + dictionaryapi.dev
✓ Falls back to large 200+ curated word list (persistent, no repeats until exhausted)
✓ Shows word (top) + scrolling definition (bottom)
✓ Caches last word and rotates fallback list
"""

import os, time, random, requests, json
from datetime import datetime
from RPLCD.i2c import CharLCD

# LCD config
LCD_DRIVER = 'PCF8574'
LCD_ADDR = 0x27
I2C_PORT = 1
COLS = 16

# Refresh interval (6 hours)
UPDATE_INTERVAL = 30
STATIC_DISPLAY = 2.0
SCROLL_STEP = 0.15
SCROLL_GAP = "    "

# Files
LAST_WORD_FILE = "/tmp/i2c_word_last.txt"
WORD_INDEX_FILE = "/tmp/i2c_word_index.txt"
LOG_FILE = "/tmp/i2c_word_improved.log"

# --- HUGE 200+ fallback list ---
FALLBACK_WORDS = [
    "aberration","absolution","abundance","accolade","acumen","adroit","aesthetic","affinity","agility","alchemy",
    "altruism","ambience","ambivalence","ameliorate","amiable","amorphous","anomaly","antithesis","aplomb","arcane",
    "ardent","articulate","ascendancy","aspiration","assiduous","audacity","austerity","benevolent","benign","bliss",
    "bravado","brevity","buoyant","cacophony","candor","capricious","catharsis","celestial","chimerical","clarity",
    "coalesce","coherent","colossal","composure","concord","confluence","conscientious","constancy","contentment",
    "convivial","copacetic","cosmic","credence","crescendo","cryptic","dauntless","debonaire","decorum","defiant",
    "delineate","demure","denouement","deviate","dexterous","diligent","discern","disparate","divergent","docile",
    "ebullient","eclectic","effervescent","efficacious","effulgent","elated","eloquent","eminent","empirical","enchanting",
    "enigma","ephemeral","epiphany","equanimity","ethereal","euphoria","evanescent","exemplary","exhilarate","exquisite",
    "facetious","fallacy","felicity","fervent","flourish","fortitude","fruition","futile","galvanize","garrulous",
    "genial","gregarious","halcyon","harbinger","harmonious","hegemony","heresy","idyllic","illustrious","impeccable",
    "impervious","impetuous","incandescent","incessant","incipient","incongruous","indelible","indigenous","indomitable",
    "ineffable","inexorable","ingenuous","innate","insatiable","insidious","insightful","insolent","integrity","intrepid",
    "intrinsic","invincible","jocular","judicious","juxtapose","kinetic","labyrinthine","laconic","lambent","lament",
    "languid","latent","laudable","levity","lucid","luminary","magnanimous","mellifluous","meticulous","mirage",
    "mirthful","modicum","mollify","myriad","nascent","nebulous","nonchalant","nostalgia","oblivion","obstinate",
    "odyssey","omnipotent","omnipresent","omniscient","opulent","ornate","ostentatious","panacea","paradox","parsimonious",
    "pejorative","penumbra","perennial","pernicious","perseverance","pertinent","petrichor","philanthropy","picturesque",
    "placid","plethora","poignant","precocious","prelude","proclivity","profound","prosaic","quandary","quell","quintessence",
    "radiant","ravenous","reclusive","redolent","refulgent","rejuvenate","relinquish","remnant","renaissance","resilient",
    "resolute","resonance","reverie","sagacious","salient","sanguine","serendipity","serene","silhouette","solace",
    "sonorous","sophrosyne","sublime","succinct","superfluous","synergy","taciturn","tenacious","tranquil","transient",
    "ubiquitous","umbrage","undulate","unfathomable","utopia","valiant","vehement","venerable","veracity","verdant",
    "verve","vigilant","vindicate","virtuoso","vociferous","volition","whimsical","winsome","wistful","zenith","zephyr",
    "zealous","zeitgeist"
]

# APIs
WORDNIK_KEY = os.environ.get("WORDNIK_KEY", "").strip()
WORDNIK_RANDOM = "https://api.wordnik.com/v4/words.json/randomWord"
WORDNIK_DEF = "https://api.wordnik.com/v4/word.json/{}/definitions"
RANDOM_WORD_API = "https://random-word-api.herokuapp.com/word?number=1"
DICTAPI = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"

# LCD init
lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=I2C_PORT, cols=COLS, rows=2)
lcd.backlight_enabled = True

# Helper functions
def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

def read_last_word():
    try:
        with open(LAST_WORD_FILE) as f:
            return f.read().strip()
    except Exception:
        return None

def write_last_word(word):
    try:
        with open(LAST_WORD_FILE, "w") as f:
            f.write(word or "")
    except Exception:
        pass

def read_word_index():
    try:
        with open(WORD_INDEX_FILE) as f:
            lines = f.read().splitlines()
            order = lines[0].split(",")
            idx = int(lines[1])
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
            f.write(",".join(order) + "\n" + str(idx))
    except Exception:
        pass

def get_next_fallback_word():
    order, idx = read_word_index()
    if idx >= len(order):
        order = FALLBACK_WORDS[:]
        random.shuffle(order)
        idx = 0
    w = order[idx]
    idx += 1
    write_word_index(order, idx)
    return w

# API fetchers
def fetch_wordnik_word():
    if not WORDNIK_KEY:
        return None
    try:
        r = requests.get(WORDNIK_RANDOM, params={"api_key": WORDNIK_KEY}, timeout=8)
        r.raise_for_status()
        j = r.json()
        return j.get("word")
    except Exception as e:
        log(f"Wordnik fail: {e}")
        return None

def fetch_wordnik_def(word):
    if not WORDNIK_KEY:
        return None
    try:
        r = requests.get(WORDNIK_DEF.format(word), params={"limit": 1, "api_key": WORDNIK_KEY}, timeout=8)
        r.raise_for_status()
        j = r.json()
        if isinstance(j, list) and j:
            return j[0].get("text")
    except Exception as e:
        log(f"Wordnik def fail: {e}")
        return None

def fetch_random_word():
    try:
        r = requests.get(RANDOM_WORD_API, timeout=6)
        r.raise_for_status()
        j = r.json()
        if isinstance(j, list) and j:
            return j[0]
    except Exception as e:
        log(f"RandomWord fail: {e}")
    return None

def fetch_dictionary_def(word):
    try:
        r = requests.get(DICTAPI.format(word), timeout=8)
        r.raise_for_status()
        j = r.json()
        if isinstance(j, list) and j:
            meanings = j[0].get("meanings", [])
            if meanings:
                defs = meanings[0].get("definitions", [])
                if defs:
                    return defs[0].get("definition")
    except Exception:
        pass
    return None

def choose_word():
    last = read_last_word()
    # Wordnik
    if WORDNIK_KEY:
        w = fetch_wordnik_word()
        if w and w.lower() != (last or "").lower():
            d = fetch_wordnik_def(w) or fetch_dictionary_def(w)
            if d:
                log(f"Using Wordnik {w}")
                return w, d
    # Random Word API
    w = fetch_random_word()
    if w and w.lower() != (last or "").lower():
        d = fetch_dictionary_def(w)
        if d:
            log(f"Using RandomWord {w}")
            return w, d
    # fallback
    w = get_next_fallback_word()
    if w.lower() == (last or "").lower():
        w = get_next_fallback_word()
    d = fetch_dictionary_def(w) or "Definition not available."
    log(f"Fallback {w}")
    return w, d

# Scroll helper
def scroll_window(full, base, now):
    if not full:
        return "".ljust(COLS)
    if len(full) <= COLS:
        return full.ljust(COLS)
    static_until = base + STATIC_DISPLAY
    if now < static_until:
        return full[:COLS].ljust(COLS)
    scroll = full + SCROLL_GAP
    total = len(scroll)
    elapsed = now - static_until
    step = int(elapsed / SCROLL_STEP)
    pos = step % total
    return (scroll + scroll)[pos:pos + COLS]

# Main
def main():
    last_fetch = 0
    header, text = "WORD", "loading..."
    base_time = 0.0
    try:
        while True:
            now = time.time()
            if now - last_fetch >= UPDATE_INTERVAL or text == "loading...":
                w, d = choose_word()
                write_last_word(w)
                header = w.upper().center(COLS)
                text = d if len(d) < 800 else d[:800] + "..."
                base_time = now
                last_fetch = now
            top = header[:COLS].ljust(COLS)
            bottom = scroll_window(text, base_time, time.time())
            try:
                lcd.cursor_pos = (0,0); lcd.write_string(top)
                lcd.cursor_pos = (1,0); lcd.write_string(bottom)
            except Exception:
                lcd.clear()
                lcd.cursor_pos = (0,0); lcd.write_string(top)
                lcd.cursor_pos = (1,0); lcd.write_string(bottom)
            time.sleep(0.12)
    except KeyboardInterrupt:
        lcd.clear()
        lcd.write_string("Stopped".ljust(COLS))
        lcd.backlight_enabled = True

if __name__ == "__main__":
    main()
