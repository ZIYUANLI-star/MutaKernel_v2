#!/usr/bin/env python3
"""WCFU stage 2: top up the __random__-position control cells to >= 20 rounds.

The n-a 15 pass left random-position control cells at exactly 15 clean rounds
(random cells contribute 1 round per replay, stress cells 2), five short of
the 20-round determinism line, so 6 witnesses on L1_P49 / L2_P68 / L2_P81
stayed PENDING_CONTROL.  Rerun those kernels' control cells with n-a 25.

Waits for WCFU_DONE (fp16 fix wave drained), then brakes, audits, re-analyzes,
releases.  Any failure leaves the brake held and writes WCFU2_BLOCKED.
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

MK = Path("/root/mk_v2")
PY = "/root/miniconda3/bin/python"
B9 = Path("/root/mk_v2_runs/e3_b9_calib")
WC = Path("/root/mk_v2_runs/e1/witness_confirmation")
LOG = B9 / "wcfu2_chain.log"
LOCKF = B9 / "wcfu2_chain.lock"
DONE = B9 / "WCFU2_DONE"
BLOCKED = B9 / "WCFU2_BLOCKED"
OWNER = "wc_followup2"
KERNELS = "L1_P49,L2_P68,L2_P81"
POLL_S = 120


def log(msg):
    line = "[wcfu2 %s] %s" % (time.strftime("%Y-%m-%dT%H:%M:%S%z"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def sh(cmd, timeout=None):
    p = subprocess.run(cmd, shell=True, timeout=timeout,
                       capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def block(reason):
    BLOCKED.write_text(json.dumps(
        {"at": datetime.now().isoformat(), "reason": reason},
        ensure_ascii=False, indent=1), encoding="utf-8")
    log("BLOCKED: %s (brake stays held)" % reason)
    sys.exit(1)


def drivers_alive():
    _, out = sh("pgrep -f '[_]b9_calib_driver_v2.py' | wc -l")
    return int(out.strip() or 0)


def gpu_apps():
    _, out = sh("nvidia-smi --query-compute-apps=pid --format=csv,noheader")
    return [l for l in out.splitlines() if l.strip()]


def main():
    handle = open(LOCKF, "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another wcfu2 chain holds the lock -> exit")
        return 0
    handle.seek(0)
    handle.truncate()
    handle.write("%d\n" % os.getpid())
    handle.flush()
    if DONE.exists():
        log("WCFU2_DONE already present -> nothing to do")
        return 0

    log("step 1: waiting for WCFU_DONE + idle lanes/GPU")
    beats = 0
    while True:
        if (B9 / "WCFU_DONE").exists() and drivers_alive() == 0 \
                and not gpu_apps():
            break
        if (B9 / "WCFU_BLOCKED").exists():
            block("upstream WCFU_BLOCKED present; not proceeding")
        beats += 1
        if beats % 15 == 0:
            log("heartbeat: wcfu_done=%s drivers=%d gpu=%d"
                % ((B9 / "WCFU_DONE").exists(), drivers_alive(),
                   len(gpu_apps())))
        time.sleep(POLL_S)
    log("fix wave drained")

    rc, out = sh('%s %s/_b9_brake.py hold %s --reason '
                 '"random-position control top-up to 25 replays" '
                 '--release-when "wcfu2 releases after re-analysis"'
                 % (PY, MK, OWNER))
    if rc != 0:
        block("brake hold failed: %s" % out[-300:])
    log("step 2: brake held by %s" % OWNER)

    log("step 3: audit --stage control --only %s --force --n-a 25" % KERNELS)
    rc, out = sh("cd %s && %s _wc_audit.py run --stage control --only %s "
                 "--force --n-a 25 --lane 0 --lanes 1" % (MK, PY, KERNELS),
                 timeout=4 * 3600)
    log("audit exit %d; tail: %s" % (rc, out[-200:].replace("\n", " | ")))
    if rc != 0:
        block("audit rc=%d" % rc)

    rc, out = sh("cd %s && %s _wc_analyze.py > %s 2>&1"
                 % (MK, PY, WC / "wcfu2_analyze_stdout.txt"), timeout=1800)
    if rc != 0:
        block("wc_analyze rc=%d" % rc)
    log("step 4: wc1_report regenerated")

    rc, out = sh("%s %s/_b9_brake.py release %s" % (PY, MK, OWNER))
    if rc != 0:
        block("brake release failed: %s" % out[-300:])
    log("step 5: brake released")

    try:
        j = json.loads((WC / "wc1_report.json").read_text(encoding="utf-8"))
        summary = {"verdict_counts": j["verdict_counts"],
                   "final_counts": j["final_counts"],
                   "control_cell_states": j["control_cell_states"]}
    except Exception as exc:
        summary = {"note": "report read failed: %s" % exc}
    DONE.write_text(json.dumps(
        {"finished_at": datetime.now().isoformat(), **summary},
        ensure_ascii=False, indent=1), encoding="utf-8")
    log("WCFU2_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
