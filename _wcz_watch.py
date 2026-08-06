"""Resilient watcher for the WC-1 audit: polls every ~20 min until both lanes
write STAGE_DONE_all_lane*, then reports whether the B9 brake was lifted.

Prints one compact status block per poll.  A failed poll is logged and retried
on the next tick; only a stalled lane (log untouched > STALL_MIN minutes with no
live worker) or completion ends the loop.
"""
from __future__ import annotations

import sys
import time
import traceback
from datetime import datetime

import _wcx

WC = "/root/mk_v2_runs/e1/witness_confirmation"
B9 = "/root/mk_v2_runs/e3_b9_calib"
POLL_S = 1200
STALL_MIN = 20

CMD = (
    "date '+%%s %%F %%T'; echo @@; "
    "ls %s/STAGE_DONE_all_lane0 %s/STAGE_DONE_all_lane1 2>/dev/null | wc -l; echo @@; "
    "for l in 0 1; do stat -c '%%Y' %s/audit_lane$l.log 2>/dev/null || echo 0; done; echo @@; "
    "for l in 0 1; do tail -n 1 %s/audit_lane$l.log 2>/dev/null; done; echo @@; "
    "ls %s/cells/*.json 2>/dev/null | wc -l; echo @@; "
    "ps -eo pid,ppid,etimes,cmd | grep -E '_wc_audit|_mutant_worker|_wc_start' "
    "| grep -v grep | wc -l; "
    "ps -eo pid,ppid,cmd | grep _mutant_worker | grep -v grep | wc -l; echo @@; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; echo @@; "
    "(grep '^oom_kill ' /sys/fs/cgroup/memory/memory.oom_control 2>/dev/null "
    "|| grep '^oom_kill ' /sys/fs/cgroup/memory.events 2>/dev/null || echo 'oom_kill NA'); "
    "cat /sys/fs/cgroup/memory/memory.failcnt 2>/dev/null || echo NA; echo @@; "
    "ls %s/PAUSED_FOR_SIGNOFF_RERUN >/dev/null 2>&1 && echo BRAKE_PRESENT || echo BRAKE_ABSENT; "
    "ls %s/brakes/ 2>/dev/null | tr '\\n' ' '; echo @@; "
    "tail -n 3 %s/starter.log" % (WC, WC, WC, WC, WC, B9, B9, WC)
)


def parse(out):
    p = [x.strip() for x in out.split("@@")]
    while len(p) < 10:
        p.append("")
    now = p[0].split()
    lane_mt = [int(x or 0) for x in p[2].splitlines() if x.strip()] or [0, 0]
    procs = [int(x) for x in p[5].split() if x.isdigit()] or [0, 0]
    return {
        "epoch": int(now[0]) if now and now[0].isdigit() else 0,
        "stamp": " ".join(now[1:]),
        "n_done": int(p[1] or 0),
        "lane_mtime": lane_mt,
        "tails": p[3],
        "cells": int(p[4] or 0),
        "n_audit": procs[0], "n_worker": procs[1] if len(procs) > 1 else 0,
        "gpu": p[6].replace("\n", " / "),
        "oom": p[7].replace("\n", " "),
        "brake": p[8],
        "starter": p[9].replace("\n", " | ")[-300:],
    }


def main():
    stalls = 0
    prev_cells = -1
    while True:
        try:
            with _wcx.Session(label="watch ") as s:
                out = s.run(CMD, timeout=150)[1]
            st = parse(out)
        except Exception as exc:
            print("[watch %s] POLL_FAILED %r -- retrying next tick"
                  % (datetime.now().strftime("%F %T"), exc), flush=True)
            traceback.print_exc()
            time.sleep(300)
            continue

        age = [round((st["epoch"] - m) / 60.0, 1) if m else -1
               for m in st["lane_mtime"]]
        print("\n[watch %s] stage_done=%d/2 cells=%d (prev %d) audit_procs=%d "
              "workers=%d log_age_min=%s\n  gpu: %s\n  oom: %s\n  brake: %s\n"
              "  tails: %s" % (st["stamp"], st["n_done"], st["cells"], prev_cells,
                               st["n_audit"], st["n_worker"], age, st["gpu"],
                               st["oom"], st["brake"],
                               st["tails"].replace("\n", "\n         ")), flush=True)

        if st["n_done"] >= 2:
            print("\nWC_STAGE_DONE_BOTH at %s" % st["stamp"], flush=True)
            print("  starter.log: %s" % st["starter"], flush=True)
            return 0

        stalled = (max(age) > STALL_MIN and st["n_worker"] == 0
                   and st["cells"] == prev_cells)
        stalls = stalls + 1 if stalled else 0
        if st["n_audit"] == 0:
            print("\nWC_ANOMALY lanes gone before STAGE_DONE", flush=True)
            return 2
        if stalls >= 2:
            print("\nWC_ANOMALY stalled: no worker, no new cell, logs older than "
                  "%d min for 2 consecutive polls" % STALL_MIN, flush=True)
            return 3

        prev_cells = st["cells"]
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
