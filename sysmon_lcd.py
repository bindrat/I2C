#!/usr/bin/env python3
# sysmon_lcd_rescroll_fixed2.py
# System monitor with reliable time-driven scrolling.
# Static pause resets only on IP or Root% changes to avoid temp jitter resets.

import time
import socket
import shutil
from RPLCD.i2c import CharLCD
import subprocess

# ---------- CONFIG ----------
LCD_DRIVER = 'PCF8574'
LCD_ADDR = 0x27
COLS = 16
ROWS = 2

REFRESH_INTERVAL = 2.0              # seconds between metric refreshes
LOOP_SLEEP = 0.12                   # main loop sleep
IP_SCROLL_STEP = 0.3                # seconds per scroll step
IP_GAP = "    "                     # gap between repeats when scrolling
STATIC_DISPLAY_AFTER_UPDATE = 2.0   # seconds to show leftmost window before scrolling
VERBOSE = False                     # set True to print debug scroll info to console

# ---------- LCD init ----------
lcd = CharLCD(LCD_DRIVER, LCD_ADDR, port=1, cols=COLS, rows=ROWS)
lcd.backlight_enabled = True

# ---------- metric readers ----------
def read_cpu_times():
    try:
        with open("/proc/stat", "r") as f:
            line = f.readline()
    except Exception:
        return None
    if not line.startswith("cpu "):
        return None
    parts = line.split()
    vals = [int(p) for p in parts[1:]]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    total = sum(vals)
    return idle, total

def get_cpu_percent(prev):
    now = read_cpu_times()
    if not now or not prev:
        return None, now
    idle_prev, total_prev = prev
    idle, total = now
    idle_delta = idle - idle_prev
    total_delta = total - total_prev
    if total_delta <= 0:
        return None, now
    usage = (1.0 - (idle_delta / total_delta)) * 100.0
    return int(round(usage)), now

def get_mem_percent():
    try:
        meminfo = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split(":")
                key = parts[0]
                value = parts[1].strip().split()[0]
                meminfo[key] = int(value)
        total = meminfo.get("MemTotal")
        avail = meminfo.get("MemAvailable", None)
        if total is None:
            return None
        if avail is None:
            free = meminfo.get("MemFree", 0)
            buffers = meminfo.get("Buffers", 0)
            cached = meminfo.get("Cached", 0)
            avail = free + buffers + cached
        used = total - avail
        return int(round((used / total) * 100.0))
    except Exception:
        return None

def get_root_fs_percent():
    try:
        du = shutil.disk_usage('/')
        return int(round((du.used / du.total) * 100.0))
    except Exception:
        return None

def read_cpu_temp():
    paths = [
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/class/hwmon/hwmon0/temp1_input",
    ]
    for p in paths:
        try:
            with open(p, "r") as f:
                raw = f.read().strip()
            if not raw:
                continue
            val = float(raw)
            return int(round(val / 1000.0)) if val > 1000 else int(round(val))
        except Exception:
            continue
    try:
        out = subprocess.check_output(["vcgencmd", "measure_temp"], stderr=subprocess.DEVNULL)
        out = out.decode("utf8").strip()
        if out.startswith("temp=") and out.endswith("'C"):
            t = out.split("=")[1].split("'")[0]
            return int(round(float(t)))
    except Exception:
        pass
    return None

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1.0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

def build_bottom_string(ip, root_pct, temp_c):
    ip_part = "IP:No network" if not ip else f"IP:{ip}"
    root_part = "Root:N/A" if root_pct is None else f"Root:{root_pct}%"
    temp_part = "T:N/A" if temp_c is None else f"T:{temp_c}C"
    return f"{ip_part} | {root_part} | {temp_part}"

# ---------- scrolling time logic ----------
# metrics_timer_ts: timestamp when static pause was (last) started
# we will reset it only when ip or root_pct changes (to avoid temp jitter).
metrics_timer_ts = 0.0
previous_ip = None
previous_root_pct = None

def bottom_window_time_driven(full_s, now_ts):
    """
    If full_s length <= COLS: return padded left-justified string.
    If longer:
      - if now_ts < metrics_timer_ts + STATIC_DISPLAY_AFTER_UPDATE:
          return leftmost COLS chars (static).
      - else compute elapsed = now_ts - (metrics_timer_ts + STATIC_DISPLAY_AFTER_UPDATE)
          step = int(elapsed / IP_SCROLL_STEP)
          pos = step % total_len
          return wrapped[pos:pos+COLS]
    """
    if len(full_s) <= COLS:
        return full_s.ljust(COLS)

    static_until = metrics_timer_ts + STATIC_DISPLAY_AFTER_UPDATE
    if now_ts < static_until:
        return full_s[:COLS].ljust(COLS)

    scroll = full_s + IP_GAP
    total_len = len(scroll)
    elapsed = now_ts - static_until
    step = int(elapsed / IP_SCROLL_STEP)
    pos = step % total_len
    wrapped = scroll + scroll
    window = wrapped[pos:pos + COLS]

    if VERBOSE:
        print(f"DEBUG scroll: elapsed={elapsed:.2f}s step={step} pos={pos} total={total_len} -> '{window}'")

    return window

def fmt_top_line(cpu_pct, mem_pct):
    cpu_s = "CPU:--%" if cpu_pct is None else f"CPU:{cpu_pct}%"
    mem_s = "MEM:--%" if mem_pct is None else f"MEM:{mem_pct}%"
    s = f"{cpu_s} {mem_s}"
    return s[:COLS].ljust(COLS)

# ---------- main ----------
def main():
    global metrics_timer_ts, previous_ip, previous_root_pct
    prev = read_cpu_times()
    time.sleep(0.2)

    try:
        last_metrics_time = 0
        ip = None
        root_pct = None
        cpu_pct = None
        mem_pct = None
        temp_c = None

        while True:
            now_ts = time.time()

            if now_ts - last_metrics_time >= REFRESH_INTERVAL:
                # refresh metrics
                cpu_pct_val, prev = get_cpu_percent(prev)
                cpu_pct = cpu_pct_val if cpu_pct_val is not None else cpu_pct

                mem_pct_val = get_mem_percent()
                mem_pct = mem_pct_val if mem_pct_val is not None else mem_pct

                root_pct_val = get_root_fs_percent()
                root_pct = root_pct_val if root_pct_val is not None else root_pct

                temp_val = read_cpu_temp()
                temp_c = temp_val if temp_val is not None else temp_c

                ip = get_ip_address()

                # Decide whether to reset the static/scroll timer.
                # Reset only if IP changed OR Root% changed.
                if previous_ip is None and previous_root_pct is None:
                    # first run: start timer
                    metrics_timer_ts = now_ts
                    previous_ip = ip
                    previous_root_pct = root_pct
                    if VERBOSE:
                        print(f"INITIAL bottom: '{build_bottom_string(ip, root_pct, temp_c)}'")
                else:
                    ip_changed = (ip != previous_ip)
                    root_changed = (root_pct != previous_root_pct)
                    if ip_changed or root_changed:
                        metrics_timer_ts = now_ts
                        previous_ip = ip
                        previous_root_pct = root_pct
                        if VERBOSE:
                            print(f"BOTTOM SIGNIFICANT CHANGE at {time.strftime('%H:%M:%S', time.localtime(now_ts))}: ip_changed={ip_changed} root_changed={root_changed}")

                last_metrics_time = now_ts

            top = fmt_top_line(cpu_pct, mem_pct)
            full_bottom = build_bottom_string(ip, root_pct, temp_c)
            bottom = bottom_window_time_driven(full_bottom, now_ts)

            # write both lines to LCD
            try:
                lcd.cursor_pos = (0, 0); lcd.write_string(top)
                lcd.cursor_pos = (1, 0); lcd.write_string(bottom)
            except Exception as e:
                # try to re-init write if odd happens
                try:
                    lcd.clear()
                    lcd.cursor_pos = (0, 0); lcd.write_string(top)
                    lcd.cursor_pos = (1, 0); lcd.write_string(bottom)
                except Exception:
                    if VERBOSE:
                        print("LCD write failed:", e)

            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        lcd.clear()
        lcd.write_string("Stopped")
        lcd.backlight_enabled = True

if __name__ == "__main__":
    main()
