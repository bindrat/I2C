#!/usr/bin/env python3
"""
i2c_rotator_by_script.py

Rotation manager that runs display scripts sequentially. Each entry in SCRIPTS can be:
 - "/full/path/to/script.py"              # uses DEFAULT_DURATION
 - ("/full/path/to/script.py", 180)       # runs 180 seconds for this script

Only one process owns the display at a time. The rotator kills each script after its duration.
"""

import subprocess
import time
import os
import signal
import sys
from datetime import datetime

# ---------- CONFIG ----------
# Edit this list to include your scripts. Use strings or (path, seconds) tuples.
# Example:
SCRIPTS = [
    ("/root/I2C/sysmon_lcd.py", 60),           # 1 minutes
    ("/root/I2C/blink.py", 2),           # 1 minutes
    ("/root/I2C/time_quote.py", 30),           # 1 minutes
    ("/root/I2C/blink.py", 2),           # 1 minutes
    ("/root/I2C/tempi2ctrend.py", 60),
    ("/root/I2C/blink.py", 2),           # 1 minutes
    ("/root/I2C/crypto.py", 30),               # 1 minutes
    ("/root/I2C/blink.py", 2),           # 1 minutes
    ("/root/I2C/gold_noapi.py", 30),                 # 1 minutes
    ("/root/I2C/blink.py", 2),           # 1 minutes
    ("/root/I2C/dollar.py", 30),               # 1 minutes
    ("/root/I2C/blink.py", 2),           # 1 minutes
    ("/root/I2C/tempi2ctrend.py", 60),
    ("/root/I2C/blink.py", 3),           # 1 minutes
#    ("/root/I2C/word_improved.py", 120),       # 2 minutes
#    ("/root/I2C/blink.py", 2),           # 1 minutes
#    ("/root/I2C/nifty.py", 200),               # 3 minutes
#    ("/root/I2C/tempi2ctrend.py", 60),
]

DEFAULT_DURATION = 300   # seconds if a script is listed as string only
SLEEP_AFTER_STOP = 0.6   # seconds to wait after stopping a script
PYTHON = "/root/lcdenv/bin/python"  # change to your venv python if needed (e.g. /root/lcdenv/bin/python)

VERBOSE = True

# ---------- helpers ----------
def log(msg):
    if VERBOSE:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def normalize_scripts(scripts):
    """Return list of (path, duration) pairs. Expand strings with default duration."""
    out = []
    for entry in scripts:
        if isinstance(entry, str):
            out.append((entry, DEFAULT_DURATION))
        elif isinstance(entry, (list, tuple)) and len(entry) >= 1:
            path = entry[0]
            dur = entry[1] if len(entry) > 1 and isinstance(entry[1], (int, float)) else DEFAULT_DURATION
            out.append((path, int(dur)))
        else:
            log(f"Skipping invalid entry in SCRIPTS: {entry}")
    return out

def make_executable(path):
    try:
        st = os.stat(path)
        os.chmod(path, st.st_mode | 0o111)
    except Exception:
        pass

def run_script(path):
    """Start the script as a subprocess and return the Popen object (or None on failure)."""
    if not os.path.isfile(path):
        log(f"Script not found: {path}")
        return None
    make_executable(path)
    try:
        p = subprocess.Popen([PYTHON, path],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             preexec_fn=os.setsid)
        log(f"Started: {path} (pid {p.pid})")
        return p
    except Exception as e:
        log(f"Failed to start {path}: {e}")
        return None

def stop_process(p):
    """Terminate a process group gracefully, then force-kill if needed."""
    if p is None:
        return
    try:
        pid = p.pid
        pgid = os.getpgid(pid)
        log(f"Stopping pid {pid} (pgid {pgid})")
        os.killpg(pgid, signal.SIGTERM)
        # wait briefly for graceful exit
        for _ in range(40):  # up to ~4s
            if p.poll() is not None:
                break
            time.sleep(0.1)
        if p.poll() is None:
            log(f"Force-killing pid {pid}")
            os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except Exception as e:
        log(f"Error stopping process: {e}")

# ---------- main loop ----------
def main():
    normalized = normalize_scripts(SCRIPTS)
    if not normalized:
        print("No scripts configured in SCRIPTS. Edit the file to add scripts.")
        sys.exit(1)

    idx = 0
    current_proc = None

    try:
        while True:
            path, duration = normalized[idx % len(normalized)]
            log(f"Next: {path} for {duration}s")
            current_proc = run_script(path)
            start_time = time.time()

            # run loop: check if process is alive and duration not exceeded
            while True:
                if current_proc is None:
                    log(f"Process for {path} failed to start; moving on.")
                    break
                if current_proc.poll() is not None:
                    log(f"Process {path} exited early (code {current_proc.returncode}).")
                    break
                elapsed = time.time() - start_time
                if elapsed >= duration:
                    log(f"Time up for {path} ({int(elapsed)}s).")
                    break
                # responsive sleep
                time.sleep(0.5)

            # stop the process if still running
            stop_process(current_proc)
            current_proc = None
            time.sleep(SLEEP_AFTER_STOP)

            idx += 1

    except KeyboardInterrupt:
        log("KeyboardInterrupt — shutting down rotator.")
        stop_process(current_proc)
        sys.exit(0)
    except Exception as e:
        log(f"Rotator error: {e}")
        stop_process(current_proc)
        raise

if __name__ == "__main__":
    main()
