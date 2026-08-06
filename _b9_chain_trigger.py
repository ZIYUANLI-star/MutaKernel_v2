#!/usr/bin/env python3
"""Chain-start the B9 calibration first wave the moment the critical path ends.

Deployed to /root/mk_v2/_b9_chain_trigger.py; run detached with

    cd /root/mk_v2 && setsid /root/miniconda3/bin/python -u _b9_chain_trigger.py \
        >> /root/mk_v2_runs/e3_b9_calib/chain_trigger_stdout.log 2>&1 < /dev/null &

Why it exists: the B9 calibration must not overlap the E1 CSE sign-off rerun (a
four-lane B9 wave OOM-killed the sign-off worker once already), but leaving the
GPU idle between the sign-off finishing and a human noticing costs hours.  The
trigger closes that gap without ever competing with the critical path.

Sequence
--------
1. wait for /root/mk_v2_runs/e1/SIGNOFF_ORCH_DONE (written by _signoff_orch.py
   only after its last requeue round);
2. re-verify the preconditions independently -- no _mutant_worker.py, no
   run_e1_cse_falsify.py, no _signoff_orch.py, no GPU compute app, plus a full
   _b9_precheck.py pass -- and require CONSECUTIVE_CLEAN consecutive clean polls,
   so a momentary gap between two critical-path units cannot be mistaken for the
   end of the run.  Every failed check is logged with its reason and the run keeps
   waiting: waiting is always cheaper than a polluted record;
3. fire `resume_b9.sh --lanes 2 --limit N`, where N is the number of units whose
   last recorded status is a failure.  That is exactly the requeue wave, because
   the deployed queue builder orders `requeued` before `fresh`; the decision to
   validate the torch.quantile fix on the requeue wave before committing to the
   full 382-unit queue is therefore enforced mechanically, not by convention;
4. stay resident as a watchdog: if the critical path ever reappears, brake with
   pause_b9.sh (lanes finish the unit in flight, record it, exit cleanly) and
   resume afterwards by lifting the marker, which is what guard_b9_v2.sh waits
   for -- deliberately *not* a second resume_b9.sh, since that would start a
   second guard and double the lane count back into the OOM regime.

Idempotency: an flock'd lock file makes a second launch exit immediately;
CHAIN_TRIGGER_FIRED records the fire, so a restart after the wave started becomes
a watchdog instead of a second start; and a B9 run already in flight at startup
is adopted rather than restarted.

Process detection is always a /proc scan that excludes this process and its
ancestors.  `pkill -f` / `pgrep -f` are banned in this campaign: the pattern
matches the ssh command line that carries it, which has already both truncated a
session and left the intended target alive.
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

MK = Path("/root/mk_v2")
PY = "/root/miniconda3/bin/python"
OUT = Path("/root/mk_v2_runs/e3_b9_calib")
E1 = Path("/root/mk_v2_runs/e1")

SIGNOFF_DONE = E1 / "SIGNOFF_ORCH_DONE"
LOG = OUT / "chain_trigger.log"
LOCK = OUT / "chain_trigger.lock"
FIRED = OUT / "CHAIN_TRIGGER_FIRED"
EXITED = OUT / "CHAIN_TRIGGER_EXIT"
PAUSE_MARKER = OUT / "PAUSED_FOR_SIGNOFF_RERUN"

LANES = 2
BUDGET_GB = 100
POLL_S = 60
CONSECUTIVE_CLEAN = 2
MAX_RESUMES = 5
CRITICAL_NEEDLES = ("_mutant_worker.py", "run_e1_cse_falsify.py", "_signoff_orch.py")
B9_NEEDLES = ("_b9_calib_driver_v2.py", "guard_b9")


def log(message: str) -> None:
    line = "[chain %s] %s" % (time.strftime("%Y-%m-%dT%H:%M:%S%z"), message)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _ppid(pid: int) -> int:
    try:
        for line in open("/proc/%d/status" % pid, encoding="utf-8"):
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def find_processes(needle: str):
    """Processes whose cmdline contains ``needle``, minus self and ancestors."""
    excluded = set()
    pid = os.getpid()
    while pid and pid != 1:
        excluded.add(pid)
        pid = _ppid(pid)
    hits = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid in excluded:
            continue
        try:
            raw = Path("/proc/%d/cmdline" % pid).read_bytes()
        except OSError:
            continue
        cmdline = raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
        if needle in cmdline:
            hits.append((pid, cmdline[:160]))
    return hits


def critical_path_processes():
    found = []
    for needle in CRITICAL_NEEDLES:
        for pid, cmdline in find_processes(needle):
            found.append((needle, pid, cmdline))
    return found


def b9_processes():
    found = []
    for needle in B9_NEEDLES:
        for pid, cmdline in find_processes(needle):
            found.append((needle, pid, cmdline))
    return found


def gpu_compute_apps():
    try:
        smi = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory",
             "--format=csv,noheader"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return ["nvidia-smi unavailable: %s" % exc]
    return [line.strip() for line in smi.stdout.splitlines() if line.strip()]


def precheck():
    """The deployed read-only precheck; authoritative gate before firing."""
    result = subprocess.run([PY, str(MK / "_b9_precheck.py"),
                             "--budget-gb", str(BUDGET_GB)],
                            capture_output=True, text=True, cwd=str(MK), timeout=600)
    return result.returncode, (result.stdout + result.stderr)


def requeue_wave_units():
    """Units whose last recorded status is a failure = the requeue wave.

    Reuses the deployed queue builder so the trigger and resume_b9.sh cannot
    disagree about what "the first wave" means.
    """
    if str(MK) not in sys.path:
        sys.path.insert(0, str(MK))
    import importlib

    prep = importlib.import_module("_b9_resume_prep")
    importlib.reload(prep)
    _kept, requeued, _fresh, _queue = prep.build("table")
    return [unit["unit"] for unit in requeued]


def start_blockers():
    """Reasons not to start a wave right now; empty list means clear."""
    reasons = []
    for needle, pid, cmdline in critical_path_processes():
        reasons.append("critical-path process alive (%s) pid=%d: %s"
                       % (needle, pid, cmdline))
    apps = gpu_compute_apps()
    if apps:
        reasons.append("GPU compute app present: %s" % "; ".join(apps))
    return reasons


def wait_for_signoff_done():
    announced = False
    while not SIGNOFF_DONE.is_file():
        if not announced:
            procs = critical_path_processes()
            log("waiting for %s; critical path: %s" % (
                SIGNOFF_DONE,
                ", ".join("%s pid=%d" % (n, p) for n, p, _ in procs) or "no process"))
            announced = True
        time.sleep(POLL_S)
    log("%s present" % SIGNOFF_DONE.name)


def wait_until_clear(use_precheck=True):
    """Require CONSECUTIVE_CLEAN consecutive clean polls, logging every blocker."""
    clean = 0
    last = None
    while clean < CONSECUTIVE_CLEAN:
        reasons = start_blockers()
        if not reasons and use_precheck:
            code, output = precheck()
            if code != 0:
                reasons = ["precheck refused (exit %d): %s" % (
                    code, " | ".join(line.strip() for line in output.splitlines()
                                     if "[FAIL]" in line))]
        if reasons:
            if reasons != last:
                for reason in reasons:
                    log("still blocked: " + reason)
                last = reasons
            clean = 0
            time.sleep(POLL_S)
            continue
        clean += 1
        last = None
        log("preconditions clear (%d/%d consecutive)" % (clean, CONSECUTIVE_CLEAN))
        if clean < CONSECUTIVE_CLEAN:
            time.sleep(POLL_S)
    log("all preconditions satisfied")


def fire(units):
    """Start the wave through the audited one-button script."""
    log("firing: resume_b9.sh --lanes %d --limit %d --budget-gb %d"
        % (LANES, len(units), BUDGET_GB))
    log("wave units (%d): %s" % (len(units), ", ".join(units)))
    result = subprocess.run(
        ["bash", str(OUT / "resume_b9.sh"), "--lanes", str(LANES),
         "--limit", str(len(units)), "--budget-gb", str(BUDGET_GB)],
        capture_output=True, text=True, cwd=str(OUT), timeout=1800)
    for line in (result.stdout + result.stderr).splitlines():
        log("  resume| " + line)
    log("resume_b9.sh exit=%d" % result.returncode)
    return result.returncode == 0 and "RESUME_STARTED" in result.stdout


def brake(reasons):
    log("BRAKE: critical path reappeared -> pause_b9.sh")
    for reason in reasons:
        log("  reason: " + reason)
    result = subprocess.run(["bash", str(OUT / "pause_b9.sh")],
                            capture_output=True, text=True, cwd=str(OUT), timeout=600)
    for line in (result.stdout + result.stderr).splitlines():
        log("  pause| " + line)


def lift_marker():
    """Resume a braked run: guard_b9_v2.sh restarts the lanes on its own.

    Calling resume_b9.sh again would start a *second* guard and thus run four
    units at once -- the configuration that caused the OOM incident.
    """
    stamp = time.strftime("%Y%m%dT%H%M%S")
    archive = OUT / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    target = archive / ("PAUSED_FOR_SIGNOFF_RERUN.lifted_%s" % stamp)
    os.replace(PAUSE_MARKER, target)
    log("pause marker lifted -> %s (guard restarts the lanes within 60s)"
        % target.name)


def lanes_done():
    return all((OUT / ("B9_CALIB_V2_DONE_LANE%d" % lane)).is_file()
               for lane in range(LANES))


def record_fire(units, resumes):
    FIRED.write_text(json.dumps({
        "fired_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "lanes": LANES,
        "budget_gb": BUDGET_GB,
        "wave": "v2_post_quantile_fix_requeue_wave",
        "limit": len(units),
        "units": units,
        "resumes_after_brake": resumes,
        "note": ("first wave = the requeued units only; the full 382-unit queue "
                 "stays unstarted until the E3 scope decision is taken"),
    }, indent=2), encoding="utf-8")


def watchdog(resumes):
    """Resident brake/resume loop until the wave drains.

    Note the asymmetry with the pre-fire gate: once B9 owns the GPU, a compute
    app is *expected*, so only critical-path processes count as a reason to brake.
    """
    log("watchdog up (resumes after brake: %d/%d)" % (resumes, MAX_RESUMES))
    while True:
        time.sleep(POLL_S)
        procs = critical_path_processes()
        if procs:
            reasons = ["critical-path process alive (%s) pid=%d: %s" % p
                       for p in procs]
            if PAUSE_MARKER.is_file():
                log("critical path present, pause marker already in place")
            else:
                brake(reasons)
            continue
        if PAUSE_MARKER.is_file():
            remaining = requeue_wave_units()
            if not remaining:
                log("wave complete; nothing left to requeue after the brake")
                return "done-after-brake"
            if resumes >= MAX_RESUMES:
                log("resume cap reached (%d); leaving the run paused for a human"
                    % MAX_RESUMES)
                return "resume-cap"
            # the braked lane may still be finishing its unit; wait for a fully
            # idle box before lifting the marker (precheck would reject the
            # still-running guard, so it is not used here)
            wait_until_clear(use_precheck=False)
            if not PAUSE_MARKER.is_file():
                continue
            guard = find_processes("guard_b9")
            resumes += 1
            if guard:
                lift_marker()
                log("resumed after brake (%d/%d) via the existing guard "
                    "(pid %s); %d units left in the wave"
                    % (resumes, MAX_RESUMES, guard[0][0], len(remaining)))
            else:
                log("no guard alive after the brake -> full restart of the "
                    "remaining %d units" % len(remaining))
                if not fire(remaining):
                    log("restart failed; leaving everything for a human")
                    return "resume-failed"
            record_fire(remaining, resumes)
            continue
        if lanes_done() and not find_processes("_b9_calib_driver_v2.py"):
            log("all lanes report DONE and no driver alive -> wave finished")
            return "done"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK, "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("another chain trigger holds %s -> exit (idempotent)" % LOCK.name)
        return 0
    handle.seek(0)
    handle.truncate()
    handle.write("%d\n" % os.getpid())
    handle.flush()

    log("=== chain trigger start pid=%d lanes=%d budget=%dGiB poll=%ds ==="
        % (os.getpid(), LANES, BUDGET_GB, POLL_S))
    resumes = 0
    if FIRED.is_file():
        log("CHAIN_TRIGGER_FIRED present -> watchdog only (no second start)")
        try:
            resumes = int(json.loads(FIRED.read_text()).get("resumes_after_brake", 0))
        except (OSError, ValueError):
            resumes = 0
    elif b9_processes():
        for needle, pid, cmdline in b9_processes():
            log("adopting a B9 run started outside this trigger: %s pid=%d: %s"
                % (needle, pid, cmdline))
        log("-> watchdog only (never start a second wave on top of a live one)")
    else:
        wait_for_signoff_done()
        wait_until_clear()
        units = requeue_wave_units()
        if not units:
            log("no requeued units left; nothing to fire")
            EXITED.write_text("nothing-to-fire %s\n"
                              % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
            return 0
        if len(units) != 13:
            log("NOTE: requeue wave is %d units, not the 13 recorded at handover"
                % len(units))
        if not fire(units):
            log("resume_b9.sh did not report RESUME_STARTED -> stop and leave "
                "everything for a human (no retry loop on an unclear state)")
            EXITED.write_text("fire-failed %s\n"
                              % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
            return 1
        record_fire(units, resumes)

    outcome = watchdog(resumes)
    log("chain trigger exit: %s" % outcome)
    EXITED.write_text("%s %s\n" % (outcome, time.strftime("%Y-%m-%dT%H:%M:%S%z")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
