#!/usr/bin/env python3
"""
i2c_rotator.py

Run a list of display scripts sequentially. Each script runs for DURATION seconds
(5 minutes by default); then it's terminated and the next script is launched.

This ensures only one process writes to the I2C display at a time.
"""

import subprocess
import time
import os
import signal
import sys
from datetime import datetime

# ---------- CONFIG ----------
# Put full absolute paths to the scripts you want to rotate.
# Edit these to match your actual script locations.
SCRIPTS = [
    "/root/I2C/sysmon_lcd.py",
    "/root/I2C/crypto.py",
    "/root/I2C/time_quote.py",            # replace with your clock/quotes script path
    "/root/I2C/nifty.py",               # or your ticker script path
]

DURATION = 3 * 60   # seconds each script runs (5 minutes)
SLEEP_AFTER_STOP = 0.5  # short pause after killing a script (seconds)

PYTHON = "/root/lcdenv/bin/python"  # system python; change if you use a venv (example: /root/lcdenv/bin/python)

VERBOSE = True

# ---------- helper functions ----------
def log(msg):
    if VERBOSE:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def run_script(path):
    """Start the script as a subprocess and return the Popen object."""
    if not os.path.isfile(path):
        log(f"Script not found: {path}")
        return None
    # ensure executable permission
    try:
        os.chmod(path, os.stat(path).st_mode | 0o111)
    except Exception:
        pass
    # Launch the script with Python
    try:
        p = subprocess.Popen([PYTHON, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
        log(f"Started: {path} (pid {p.pid})")
        return p
    except Exception as e:
        log(f"Failed to start {path}: {e}")
        return None

def stop_process(p):
    """Terminate process group cleanly, then force kill if needed."""
    if p is None:
        return
    try:
        pg = os.getpgid(p.pid)
        log(f"Stopping pid {p.pid} (pg {pg})")
        os.killpg(pg, signal.SIGTERM)
        # give it a moment
        for _ in range(20):
            if p.poll() is not None:
                break
            time.sleep(0.1)
        if p.poll() is None:
            log(f"Terminating pid {p.pid} (force)")
            os.killpg(pg, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except Exception as e:
        log(f"Error stopping process {p.pid}: {e}")

# ---------- main loop ----------
def main():
    if not SCRIPTS:
        print("No scripts configured in SCRIPTS list. Edit the file to add scripts.")
        sys.exit(1)

    idx = 0
    current_proc = None

    try:
        while True:
            script = SCRIPTS[idx % len(SCRIPTS)]
            # start script
            current_proc = run_script(script)
            start_time = time.time()

            # run for DURATION seconds (but re-check process is alive)
            while True:
                # if process died early, break and move to next script
                if current_proc is None:
                    log(f"Process for {script} did not start. Moving on.")
                    break
                if current_proc.poll() is not None:
                    log(f"Process {script} exited early with code {current_proc.returncode}.")
                    break
                elapsed = time.time() - start_time
                if elapsed >= DURATION:
                    log(f"Time up for {script} ({int(elapsed)}s).")
                    break
                # sleep small interval to be responsive
                time.sleep(0.5)

            # stop process
            stop_process(current_proc)
            current_proc = None
            # short pause to let display settle
            time.sleep(SLEEP_AFTER_STOP)

            # move to next script
            idx += 1

    except KeyboardInterrupt:
        log("KeyboardInterrupt received — shutting down.")
        stop_process(current_proc)
        sys.exit(0)
    except Exception as e:
        log(f"Rotator exception: {e}")
        stop_process(current_proc)
        raise

if __name__ == "__main__":
    main()
