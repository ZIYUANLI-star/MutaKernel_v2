"""Hang-proof watchdog for the CSE run: each cycle runs in a subprocess with a
hard timeout (paramiko deadlocks after machine sleep cannot freeze the parent),
and INCONCLUSIVE counts are tracked across cycles so any growth raises an alert
for immediate root-cause analysis and requeue.
"""
import subprocess
import sys
import time
from datetime import datetime

INTERVAL_S = 600
CYCLE_TIMEOUT_S = 240

last_inc = {}


def parse_inccounts(line):
    counts = {}
    for tok in line.split()[1:]:
        if "=" in tok:
            lane, n = tok.split("=", 1)
            try:
                counts[lane] = int(n)
            except ValueError:
                pass
    return counts


def main():
    global last_inc
    while True:
        try:
            res = subprocess.run(
                [sys.executable, "-u", "_watch_cse_cycle.py"],
                capture_output=True, text=True, timeout=CYCLE_TIMEOUT_S)
            out = (res.stdout or "").strip()
            done = False
            for line in out.splitlines():
                if line.startswith("INCCOUNTS"):
                    counts = parse_inccounts(line)
                    grown = {k: (last_inc.get(k, 0), v) for k, v in counts.items()
                             if v > last_inc.get(k, v)}
                    if grown:
                        detail = ", ".join(f"{k}: {a}->{b}" for k, (a, b) in grown.items())
                        print(f"ALERT_INCONCLUSIVE_GROWTH: {detail}", flush=True)
                    last_inc = counts
                    print(f"[{datetime.now():%H:%M}] {line}", flush=True)
                else:
                    print(f"[{datetime.now():%H:%M}] {line}", flush=True)
                    if "CSE_ALL_DONE" in line:
                        done = True
            if res.stderr and "UserWarning" not in res.stderr:
                print(f"[{datetime.now():%H:%M}] cycle stderr: {res.stderr.strip()[:300]}",
                      flush=True)
            if done:
                break
        except subprocess.TimeoutExpired:
            print(f"[{datetime.now():%H:%M}] WARN cycle killed after {CYCLE_TIMEOUT_S}s "
                  "(hang guard)", flush=True)
        except Exception:
            import traceback
            print(f"[{datetime.now():%H:%M}] WATCHDOG_ERROR (loop continues):", flush=True)
            traceback.print_exc()
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
