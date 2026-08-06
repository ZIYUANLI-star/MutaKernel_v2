#!/usr/bin/env python3
"""Start the WC-1 audit the moment the B9 lanes have drained, and hold the brake.

Why a keeper loop: _b9_chain_trigger.py has a "resume after brake" path (5
allowances) that lifts PAUSED_FOR_SIGNOFF_RERUN as soon as it sees two
consecutive clean polls, which happened during a 2.6-minute gap between audit
worker processes.  This keeper re-writes the *documented* pause marker whenever
it is missing while the audit is still running.  It does not touch the trigger,
the guard, or resume_b9.sh, and it stops re-writing (and lifts the marker) as
soon as both audit lanes have written their STAGE_DONE files -- at which point
the existing guard restarts the lanes on its own.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

MK = Path("/root/mk_v2")
RUNS = Path("/root/mk_v2_runs")
OUTDIR = RUNS / "e1" / "witness_confirmation"
B9 = RUNS / "e3_b9_calib"
MARKER = B9 / "PAUSED_FOR_SIGNOFF_RERUN"
LOG = OUTDIR / "starter.log"
PY = "/root/miniconda3/bin/python"
LANES = 2
N_A, N_B = 10, 20
MARKER_TEXT = (
    "Paused %s by _wc_start.py (WC-1 witness-confirmation audit owns the GPU).\n"
    "Lanes stop after the unit in flight; the guard will not restart them while\n"
    "this file exists.  _wc_start.py lifts it automatically when the audit is\n"
    "done, and the existing guard then restarts the lanes within 60s.\n"
    "Do NOT run resume_b9.sh: it would start a second guard.\n")


def log(msg):
    line = "[wc-start %s] %s" % (datetime.now().strftime("%F %T"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _ppid(pid):
    try:
        for line in open("/proc/%d/status" % pid, encoding="utf-8"):
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def scan(needle):
    excluded, pid = set(), os.getpid()
    while pid and pid != 1:
        excluded.add(pid)
        pid = _ppid(pid)
    hits = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) in excluded:
            continue
        try:
            raw = Path("/proc/%s/cmdline" % entry).read_bytes()
        except OSError:
            continue
        cmd = raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
        if needle in cmd:
            hits.append((int(entry), cmd[:150]))
    return hits


def ensure_marker():
    if not MARKER.exists():
        MARKER.write_text(MARKER_TEXT % datetime.now().strftime("%F %T %z"),
                          encoding="utf-8")
        return True
    return False


def stage_done():
    return all((OUTDIR / ("STAGE_DONE_all_lane%d" % l)).exists() for l in range(LANES))


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    log("=== starter pid=%d ===" % os.getpid())
    ensure_marker()

    deadline = time.time() + 6 * 3600
    while time.time() < deadline:
        drivers = scan("_b9_calib_driver")
        if not drivers:
            break
        log("B9 lanes still draining: %s"
            % ", ".join("pid=%d" % p for p, _ in drivers))
        ensure_marker()
        time.sleep(30)
    else:
        log("ABORT: B9 lanes did not drain within 6h")
        return 2
    log("B9 drained; GPU is free -> launching %d audit lanes" % LANES)

    for lane in range(LANES):
        cmd = ("cd %s && setsid %s -u _wc_audit.py run --stage all "
               "--n-a %d --n-b %d --lane %d --lanes %d "
               "> %s/lane%d_stdout.log 2>&1 < /dev/null &"
               % (MK, PY, N_A, N_B, lane, LANES, OUTDIR, lane))
        subprocess.Popen(["bash", "-c", cmd], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        time.sleep(5)

    log("lanes launched; holding the brake until both STAGE_DONE files appear")
    while not stage_done():
        if ensure_marker():
            log("pause marker had been lifted (chain trigger brake-resume) "
                "-> re-written; the audit still owns the GPU")
        alive = scan("_wc_audit.py")
        if not alive:
            log("WARNING: no audit lane alive and STAGE_DONE missing -> stop "
                "holding the brake and leave the decision to a human")
            return 3
        time.sleep(30)

    log("both audit lanes done -> lifting the pause marker so the EXISTING "
        "guard restarts the B9 lanes (resume_b9.sh is deliberately not used)")
    if MARKER.exists():
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        (B9 / "archive").mkdir(parents=True, exist_ok=True)
        MARKER.rename(B9 / "archive" / ("PAUSED_FOR_SIGNOFF_RERUN.lifted_wc1_%s" % stamp))
        log("lifted -> archive/PAUSED_FOR_SIGNOFF_RERUN.lifted_wc1_%s" % stamp)
    (OUTDIR / "STARTER_DONE").write_text(datetime.now().isoformat(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
