"""Watchdog for the remote E0 run5 rerun on the A800.

Polls every 15 minutes; prints one status line per cycle and an ALERT line
when something needs intervention (crash, stall, low control pass rate).
Prints RUN5_DONE when the driver reports completion.
"""
import json
import time
from datetime import datetime

import _remote

TAG = "run5"
LOG = f"/root/mk_v2_runs/e0_{TAG}_s0.log"
RUN_DIR = f"/root/mk_v2_runs/e0_{TAG}_s0"
INTERVAL_S = 900
STALL_S = 2400  # stateful probes may take ~20+ min incl. controls

consecutive_conn_failures = 0

REMOTE_CMD = (
    f"tail -c 2000 {LOG} 2>/dev/null; echo __SEP__; "
    f"wc -l < {RUN_DIR}/observations.jsonl 2>/dev/null; echo __SEP__; "
    f"cat {RUN_DIR}/original_controls.json 2>/dev/null; echo __SEP__; "
    f"stat -c %Y {LOG} 2>/dev/null; date +%s; echo __SEP__; "
    "ps aux | grep 'run_e0_flip_[r]erun' | wc -l; echo __SEP__; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"
)


def cycle():
    global consecutive_conn_failures
    try:
        c = _remote.connect()
        _, out, _ = _remote.run(c, REMOTE_CMD, timeout=120, echo=False)
        c.close()
        consecutive_conn_failures = 0
    except Exception as exc:
        consecutive_conn_failures += 1
        print(f"[{datetime.now():%H:%M}] WARN connection failed "
              f"({consecutive_conn_failures}x): {type(exc).__name__}: {str(exc)[:120]}",
              flush=True)
        if consecutive_conn_failures >= 3:
            print("ALERT: three consecutive connection failures", flush=True)
        return

    parts = out.split("__SEP__")
    tail = parts[0] if len(parts) > 0 else ""
    obs_n = (parts[1].strip() or "0") if len(parts) > 1 else "0"
    controls_raw = parts[2].strip() if len(parts) > 2 else ""
    times = parts[3].split() if len(parts) > 3 else []
    procs = int(parts[4].strip() or 0) if len(parts) > 4 else 0
    gpu = parts[5].strip() if len(parts) > 5 else "?"

    done = "DONE:" in tail

    ctrl_total = ctrl_decisive = 0
    if controls_raw:
        try:
            controls = json.loads(controls_raw)
            ctrl_total = len(controls)
            ctrl_decisive = sum(
                1 for v in controls.values()
                if v.get("corrected", {}).get("status") in ("survived", "killed"))
        except Exception:
            pass

    stall_s = None
    if len(times) >= 2:
        try:
            stall_s = int(times[-1]) - int(times[0])
        except ValueError:
            pass

    rate = f"{ctrl_decisive}/{ctrl_total}" if ctrl_total else "n/a"
    print(f"[{datetime.now():%H:%M}] probes_done={obs_n} controls_decisive={rate} "
          f"procs={procs} log_age_s={stall_s} gpu={gpu}", flush=True)

    if done:
        print("RUN5_DONE: driver reported completion", flush=True)
        return "done"
    if procs == 0:
        print("ALERT: no driver process running and no DONE marker (crash?)", flush=True)
    elif stall_s is not None and stall_s > STALL_S:
        print(f"ALERT: log stalled for {stall_s}s (> {STALL_S}s)", flush=True)
    # run4 decisive rate was 19/67; alert only if the fixed substrate is not
    # clearly better once enough controls have accumulated
    if ctrl_total >= 15 and ctrl_decisive / ctrl_total < 0.4:
        print(f"ALERT: control decisive rate low ({ctrl_decisive}/{ctrl_total})", flush=True)


def main():
    while True:
        if cycle() == "done":
            break
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
