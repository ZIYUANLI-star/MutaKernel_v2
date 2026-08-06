#!/usr/bin/env python3
"""Stage-2 auto-chain: once the requeue_final run (RQ7) completes cleanly,
promote the 44 deferred >=60GiB B9 calibration units into the pending queue
and restart the v2 guard (2 lanes, BUDGET_GB=240).

Advisor decision 2026-08-01: stage-2 is launched right after the production
requeues so that (a) the fp16-fragility ratio can be computed over the full
calibrated set and (b) the E3 B9 row has tolerances for every subject.

Fail-safe: any unexpected state writes S2_CHAIN_BLOCKED and exits without
touching the queue.
"""
import fcntl
import json
import os
import shutil
import statistics
import subprocess
import time
import traceback
from datetime import datetime
from pathlib import Path

B9 = Path("/root/mk_v2_runs/e3_b9_calib")
E1 = Path("/root/mk_v2_runs/e1")
LOG = B9 / "s2_chain.log"
QUEUE = B9 / "queue_state.json"

WAIT_POLL_S = 120
WAIT_MAX_H = 12
LANES = 2
BUDGET_GB = 240


def log(msg):
    line = "[%s] %s" % (datetime.now().isoformat(), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True,
                          text=True).stdout.strip()


def gpu_mem_mib():
    out = sh("nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits")
    try:
        return int(out.splitlines()[0].strip())
    except Exception:
        return 999999


def blocked(reason):
    log("BLOCKED: " + reason)
    (B9 / "S2_CHAIN_BLOCKED").write_text(reason)
    raise SystemExit(1)


def main():
    log("s2 chain up: waiting for RQ7 completion")
    t0 = time.time()
    while True:
        if (E1 / "requeue_final" / "RQ7_BLOCKED").exists():
            blocked("RQ7_BLOCKED marker present")
        rq_alive = sh("pgrep -c -f '[_]rq7_requeue.py'") or "0"
        done = (E1 / "requeue_final" / "RQ7_DONE").exists()
        if done and rq_alive == "0" and gpu_mem_mib() < 1024:
            log("RQ7 done, requeue process gone, GPU idle -> proceeding")
            break
        if time.time() - t0 > WAIT_MAX_H * 3600:
            blocked("timed out after %dh waiting for RQ7" % WAIT_MAX_H)
        if int(time.time() - t0) % 1800 < WAIT_POLL_S:
            log("waiting... rq7_done=%s rq7_alive=%s gpu=%sMiB"
                % (done, rq_alive, gpu_mem_mib()))
        time.sleep(WAIT_POLL_S)

    # preconditions
    if (B9 / "PAUSED_FOR_SIGNOFF_RERUN").exists():
        blocked("PAUSED_FOR_SIGNOFF_RERUN present")
    if sh("pgrep -c -f '[_]b9_calib_driver_v2.py'") not in ("", "0"):
        blocked("driver already alive")
    if sh("pgrep -c -f '[g]uard_b9_v2.sh'") not in ("", "0"):
        blocked("guard already alive")

    # queue mutation under lock, with backup
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    lock_handle = open(str(QUEUE) + ".lock", "a+")
    fcntl.flock(lock_handle, fcntl.LOCK_EX)
    try:
        shutil.copy2(QUEUE, B9 / ("queue_state.json.bak_s2_" + ts))
        qs = json.loads(QUEUE.read_text(encoding="utf-8"))
        s2 = qs.get("stage2_deferred") or []
        if not s2:
            blocked("stage2_deferred is empty; nothing to promote")

        # stage-1 convention for unit_timeout_s relative to est_wall_s_slow
        ratios = []
        for spec in qs["units"].values():
            t, e = spec.get("unit_timeout_s"), spec.get("est_wall_s_slow")
            if t and e:
                ratios.append(t / e)
        ratio = statistics.median(ratios) if ratios else 2.5
        log("timeout ratio from stage-1: median=%.2f (n=%d)" % (ratio, len(ratios)))

        promoted = []
        for spec in s2:
            uid = spec["unit"]
            if spec.get("unit_timeout_s") is None:
                spec["unit_timeout_s"] = int(max(
                    7200, ratio * (spec.get("est_wall_s_slow") or 14400)))
            qs["units"][uid] = spec
            if uid not in qs["pending"] and uid not in qs.get("done", {}):
                qs["pending"].append(uid)
                promoted.append(uid)
        qs["stage2_deferred"] = []
        qs["wave"] = "v2_stage2_large"
        qs["stage2_promoted_at"] = datetime.now().isoformat()

        tmp = B9 / "queue_state.json.tmp"
        tmp.write_text(json.dumps(qs, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, QUEUE)
        log("promoted %d stage-2 units into pending" % len(promoted))
        (B9 / "s2_promote_manifest.json").write_text(json.dumps({
            "at": datetime.now().isoformat(), "wave": "v2_stage2_large",
            "units": promoted, "lanes": LANES, "budget_gb": BUDGET_GB,
            "timeout_ratio": ratio}, indent=1), encoding="utf-8")
    finally:
        fcntl.flock(lock_handle, fcntl.LOCK_UN)
        lock_handle.close()

    for lane in range(LANES):
        marker = B9 / ("B9_CALIB_V2_DONE_LANE%d" % lane)
        if marker.exists():
            marker.rename(B9 / ("B9_CALIB_V2_DONE_LANE%d.stage1_%s" % (lane, ts)))

    subprocess.Popen(
        "cd %s && nohup env LANES=%d BUDGET_GB=%d bash guard_b9_v2.sh "
        ">> guard_b9_v2_stage2.out 2>&1 < /dev/null &" % (B9, LANES, BUDGET_GB),
        shell=True)
    time.sleep(10)
    n_guard = sh("pgrep -c -f '[g]uard_b9_v2.sh'")
    log("guard launched (instances=%s)" % n_guard)
    if n_guard in ("", "0"):
        blocked("guard failed to start")
    (B9 / "S2_CHAIN_FIRED").write_text(datetime.now().isoformat())
    log("S2_CHAIN_FIRED; stage-2 running under guard")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        log("FATAL:\n" + traceback.format_exc())
        (B9 / "S2_CHAIN_BLOCKED").write_text(traceback.format_exc())
        raise
