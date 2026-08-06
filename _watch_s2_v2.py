"""Hang-proof stage-2 watcher: each poll is a subprocess with hard timeout.

Sentinels: S2_ALL_DONE (both lane DONE markers), S2_STALL (no drivers with
work left), S2_ERR_SPIKE (run_error count grew -> OOM churn recurrence).
"""
import subprocess
import sys
import time

baseline_err = None
misses = 0
while True:
    stamp = time.strftime("%H:%M:%S")
    try:
        r = subprocess.run([sys.executable, "_s2_probe_once.py"],
                           capture_output=True, text=True, timeout=150)
        line = next((l for l in r.stdout.splitlines()
                     if l.startswith("done0=")), None)
        if line is None:
            misses += 1
            print("[%s] probe gave no status (%d misses) stderr=%s" % (
                stamp, misses, r.stderr.strip()[-200:]), flush=True)
        else:
            misses = 0
            print("[%s] %s" % (stamp, line), flush=True)
            if "done0=True done1=True" in line:
                print("S2_ALL_DONE", flush=True)
                break
            if "drivers=0" in line and " pending 0 " not in line:
                print("S2_STALL drivers gone with work left", flush=True)
            try:
                err = int(line.rsplit("run_error_latest", 1)[1].split()[0])
                if baseline_err is None:
                    baseline_err = err
                elif err > baseline_err:
                    print("S2_ERR_SPIKE run_error %d -> %d" % (baseline_err, err),
                          flush=True)
                    baseline_err = err
            except (IndexError, ValueError):
                pass
    except subprocess.TimeoutExpired:
        misses += 1
        print("[%s] probe timed out (%d misses)" % (stamp, misses), flush=True)
    if misses >= 6:
        print("S2_STALL local probe failing repeatedly", flush=True)
        misses = 0
    time.sleep(1200)
