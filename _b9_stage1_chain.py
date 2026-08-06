#!/usr/bin/env python3
"""Resident supervisor for the B9 calibration run: brake duty, gate, stage 1.

Deployed to /root/mk_v2/_b9_stage1_chain.py; run detached with

    cd /root/mk_v2 && setsid /root/miniconda3/bin/python -u _b9_stage1_chain.py \
        >> /root/mk_v2_runs/e3_b9_calib/stage1_chain_stdout.log 2>&1 < /dev/null &

It took over every live duty of _b9_chain_trigger.py, which has been retired
because its brake handling was ownership-blind: it lifted whatever
PAUSED_FOR_SIGNOFF_RERUN it found after two clean polls, which silently released
brakes placed by other parties whose workers happened to have a gap.  Braking
here goes through _b9_brake.py, where every hold is signed and only its own owner
releases it, so that failure mode no longer exists rather than being made less
likely.

Duties
------
* brake for a reappearing critical path, and release *only our own* hold once it
  is gone for CONSECUTIVE_CLEAN polls;
* keep the deployed guard alive while there is work and no brake;
* judge the first wave against the gate below and, if it passes, start stage 1
  (the 336 units reserving < 60 GiB) with 2 lanes, the 100 GiB admission budget
  and 24 intra-op threads -- the same configuration the first wave ran;
* never start stage 2: the 46 units reserving >= 60 GiB are recorded in
  queue_state.json:stage2_deferred and wait for a human decision.

Validation gate for the first wave (all must hold)
--------------------------------------------------
G1  every unit of the wave has exactly one v2 row;
G2  no row is a code-level failure (run_error_crash / driver_exception /
    control_timeout);
G3  no unit of the stage-1 size class was SIGKILLed, and the cgroup oom_kill
    counter rose by at most one per anticipated big-unit kill.  A host OOM on a
    small or medium unit means the memory model under-predicts; on one of the
    two >= 60 GiB units in the wave it is the resource boundary the calibration
    ruling already anticipated, and it does not stall the rest;
G4  measured peak RSS / estimated peak <= the 1.3 reservation safety factor for
    every unit reporting both, over at least MIN_MEMORY_SAMPLES measurements;
G5  every refined status is a real calibration outcome.

Failure mode is deliberately asymmetric.  Brakes live in files, not in this
process, and _b9_brake.sync() removes the derived marker only after positively
observing an empty holder set; there is no cleanup-on-exit path.  So if this
process dies while a brake is held, the brake stays in force and the lanes stay
stopped.  Dying means "stays braked", never "brake released".  A keepalive
(keepalive_stage1.sh) restarts it; the flock below makes a double launch a no-op.
"""
from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

MK = Path("/root/mk_v2")
PY = "/root/miniconda3/bin/python"
OUT = Path("/root/mk_v2_runs/e3_b9_calib")

LOG = OUT / "stage1_chain.log"
LOCK = OUT / "stage1_chain.lock"
GATE_REPORT = OUT / "STAGE1_GATE_REPORT.json"
BLOCKED = OUT / "STAGE1_BLOCKED"
STAGE1_FIRED = OUT / "STAGE1_FIRED"
STAGE1_DONE = OUT / "STAGE1_DONE"

BRAKE_OWNER = "critical_path"
LANES = 2
BUDGET_GB = 100.0
STAGE1_MAX_RESERVE_GB = 60.0
MEMORY_SAFETY_FACTOR = 1.3
MIN_MEMORY_SAMPLES = 8
OOM_KILL_BASELINE = 20
POLL_S = 60
CONSECUTIVE_CLEAN = 2

BLOCKING_STATUSES = ("run_error_crash", "control_timeout", "driver_exception",
                     "controls_incomplete_unresolved")
ACCEPTABLE_STATUSES = ("calibrated_ok", "calibrated_heavy_tail",
                       "protocol_undecidable_overflow",
                       "protocol_undecidable_nan")
OOM_TOLERATED_ABOVE_RESERVE_GB = STAGE1_MAX_RESERVE_GB


def log(message: str) -> None:
    line = "[stage1 %s] %s" % (time.strftime("%Y-%m-%dT%H:%M:%S%z"), message)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _import(name):
    if str(MK) not in sys.path:
        sys.path.insert(0, str(MK))
    import importlib
    module = importlib.import_module(name)
    importlib.reload(module)
    return module


def oom_kill_count():
    for path in ("/sys/fs/cgroup/memory.events",
                 "/sys/fs/cgroup/memory/memory.oom_control"):
        try:
            for line in open(path, encoding="utf-8"):
                if line.startswith("oom_kill "):
                    return int(line.split()[1])
        except OSError:
            continue
    return None


# ---------------------------------------------------------------------------
# brake duty
# ---------------------------------------------------------------------------

class BrakeDuty:
    """Hold a signed brake while the critical path runs; release only our own."""

    def __init__(self, brake):
        self.brake = brake
        self.clean = 0

    def poll(self):
        procs = self.brake.critical_path_processes()
        held = [o for o, _ in self.brake.own_holders()]
        if procs:
            self.clean = 0
            if BRAKE_OWNER not in held:
                reasons = "; ".join("%s pid=%d" % (n, p) for n, p, _ in procs)
                self.brake.hold(
                    BRAKE_OWNER,
                    "critical-path process alive: %s" % reasons,
                    "automatically, once no critical-path process and no GPU "
                    "compute app have been seen for %d consecutive polls"
                    % CONSECUTIVE_CLEAN)
                log("brake held as %r: %s" % (BRAKE_OWNER, reasons))
            return
        if BRAKE_OWNER not in held:
            self.brake.sync()
            return
        apps = self.brake.gpu_compute_apps()
        if apps and not self.brake.find_processes("calib_driver_v2.py"):
            self.clean = 0
            return
        self.clean += 1
        if self.clean < CONSECUTIVE_CLEAN:
            log("critical path clear (%d/%d) -- holding our brake a little "
                "longer" % (self.clean, CONSECUTIVE_CLEAN))
            return
        ok, message = self.brake.release(BRAKE_OWNER)
        log("released our own brake %r: %s" % (BRAKE_OWNER, message))
        self.clean = 0
        if not ok:
            log("release refused; leaving the brake in place")


def braked(brake) -> bool:
    current, _foreign = brake.sync()
    return bool(current)


def brake_summary(brake) -> str:
    current, _foreign = brake.sync()
    return ", ".join("%s%s" % (owner, "(tracked)" if rec.get("tracked_not_owned")
                               else "") for owner, rec in current) or "clear"


# ---------------------------------------------------------------------------
# run state
# ---------------------------------------------------------------------------

def queue_state():
    try:
        return json.loads((OUT / "queue_state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def wave_units():
    state = queue_state()
    return sorted(state["units"]) if state and state.get("units") else None


def wave_drained():
    state = queue_state()
    if not state:
        return False
    return not state.get("pending") and not state.get("claimed")


def v2_rows():
    rows = {}
    for path in sorted(OUT.glob("calibration_v2_lane*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                row["_source"] = path.name
                rows.setdefault(row["unit"], []).append(row)
    return rows


def start_guard(brake):
    """Start the audited guard, refusing to create a second one."""
    alive = brake.find_processes("guard_b9")
    if alive:
        log("guard already alive %s -- not starting a second one"
            % [p for p, _ in alive])
        return None
    for marker in OUT.glob("B9_CALIB_V2_DONE_LANE*"):
        marker.unlink()
        log("cleared stale marker %s" % marker.name)
    environment = {**os.environ, "LANES": str(LANES),
                   "BUDGET_GB": "%d" % BUDGET_GB}
    with open(OUT / "guard_b9_v2.log", "a", encoding="utf-8") as handle:
        handle.write("=== stage1 chain starting the guard %s ===\n"
                     % time.strftime("%F %T"))
    process = subprocess.Popen(
        ["bash", str(OUT / "guard_b9_v2.sh")], cwd=str(OUT), env=environment,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, start_new_session=True)
    log("guard started pid=%d (%d lanes, %.0f GiB budget)"
        % (process.pid, LANES, BUDGET_GB))
    return process.pid


def keep_guard_alive(brake):
    """Duty inherited from the retired trigger: a dead guard means no progress."""
    if braked(brake) or wave_drained():
        return
    if brake.find_processes("guard_b9") or brake.find_processes("calib_driver_v2.py"):
        return
    log("no guard and no lane alive while work remains -> restarting the guard")
    start_guard(brake)


# ---------------------------------------------------------------------------
# gate
# ---------------------------------------------------------------------------

def unit_reservations():
    state = queue_state()
    if not state:
        return {}
    return {unit: float(spec.get("reserve_gb") or 0.0)
            for unit, spec in state.get("units", {}).items()}


def evaluate_gate(units, rows):
    aggregate = _import("_b9_aggregate")
    checks, blockers = [], []
    reservations = unit_reservations()
    tolerated_oom = 0

    duplicated = {u: len(rows[u]) for u in units if len(rows.get(u, [])) > 1}
    if duplicated:
        blockers.append("G1 duplicate v2 rows: %s" % duplicated)
    checks.append({"check": "G1 one v2 row per unit", "units": len(units),
                   "duplicated": duplicated})

    details = []
    for unit in units:
        row = rows[unit][-1]
        status, why = aggregate.refine_status(row)
        est = row.get("est_peak_gb") or 0.0
        act = row.get("unit_peak_rss_gb") or 0.0
        ratio = (act / est) if est else None
        reserve = reservations.get(unit) or (est * MEMORY_SAFETY_FACTOR)
        details.append({
            "unit": unit, "recorded_status": row.get("control_status"),
            "status": status, "why": why, "exit_code": row.get("exit_code"),
            "cases": row.get("cases"), "outcome_kinds": row.get("outcome_kinds"),
            "calibrated_tol": row.get("calibrated_tol"),
            "est_peak_gb": est, "unit_peak_rss_gb": act, "reserve_gb": reserve,
            "peak_over_estimate": None if ratio is None else round(ratio, 3),
            "wall_s": row.get("wall_s"),
        })
        if status == "run_error_host_oom":
            if reserve >= OOM_TOLERATED_ABOVE_RESERVE_GB:
                tolerated_oom += 1
                log("G3 %s was SIGKILLed at a %.1f GiB reservation: recorded as "
                    "the resource boundary of the port, not a memory-model "
                    "deviation; stage 1 continues" % (unit, reserve))
            else:
                blockers.append(
                    "G3 %s: SIGKILL on a stage-1-class unit (%.1f GiB "
                    "reservation) -- the memory model under-predicts"
                    % (unit, reserve))
        elif status in BLOCKING_STATUSES:
            blockers.append("G2 %s: %s (%s)" % (unit, status, why))
        elif status not in ACCEPTABLE_STATUSES:
            blockers.append("G5 %s: unexpected status %s" % (unit, status))
        if ratio is not None and ratio > MEMORY_SAFETY_FACTOR:
            blockers.append(
                "G4 %s: measured peak %.1f GB is %.2fx the %.1f GB estimate, "
                "above the %.1f reservation safety factor"
                % (unit, act, ratio, est, MEMORY_SAFETY_FACTOR))

    oom = oom_kill_count()
    allowed = OOM_KILL_BASELINE + tolerated_oom
    if oom is not None and oom > allowed:
        blockers.append(
            "G3 cgroup oom_kill is %d, above the %d allowed (baseline %d plus "
            "%d anticipated big-unit kills)" % (oom, allowed, OOM_KILL_BASELINE,
                                                tolerated_oom))
    checks.append({"check": "G3 cgroup oom_kill", "value": oom,
                   "baseline": OOM_KILL_BASELINE,
                   "tolerated_big_unit_kills": tolerated_oom,
                   "allowed": allowed})

    ratios = [d["peak_over_estimate"] for d in details
              if d["peak_over_estimate"] is not None]
    checks.append({
        "check": "G4 memory model actual/estimate", "n": len(ratios),
        "min": min(ratios) if ratios else None,
        "median": sorted(ratios)[len(ratios) // 2] if ratios else None,
        "max": max(ratios) if ratios else None,
        "safety_factor": MEMORY_SAFETY_FACTOR,
    })
    if len(ratios) < MIN_MEMORY_SAMPLES:
        blockers.append(
            "G4 only %d unit(s) reported both an estimate and a peak RSS; the "
            "memory model needs at least %d measurements before a 336-unit wave"
            % (len(ratios), MIN_MEMORY_SAMPLES))

    report = {
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "wave": "v2_post_quantile_fix_requeue_wave",
        "units": len(units), "passed": not blockers, "blockers": blockers,
        "checks": checks, "per_unit": details,
    }
    GATE_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True),
                           encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# stage 1
# ---------------------------------------------------------------------------

def build_stage1_queue():
    prep = _import("_b9_resume_prep")
    kept, requeued, fresh, queue = prep.build("table")
    stage1 = [u for u in queue if u["reserve_gb"] < STAGE1_MAX_RESERVE_GB]
    stage2 = [u for u in queue if u["reserve_gb"] >= STAGE1_MAX_RESERVE_GB]

    stamp = time.strftime("%Y%m%dT%H%M%S")
    archive = OUT / "archive" / ("pre_stage1_" + stamp)
    archive.mkdir(parents=True, exist_ok=True)
    for pattern in ("calibration_lane*.jsonl", "completed_lane*.json",
                    "calibration_v2_lane*.jsonl", "completed_v2_lane*.json",
                    "queue_state.json", "lane_v2_*.log", "guard_b9_v2.log",
                    "CHAIN_TRIGGER_FIRED", "STAGE1_GATE_REPORT.json"):
        for path in sorted(OUT.glob(pattern)):
            shutil.copy2(path, archive / path.name)
    log("archived the first-wave records verbatim -> %s" % archive)

    state_path = OUT / "queue_state.json"
    state_path.write_text(json.dumps({
        "created_at": stamp,
        "wave": "v2_stage1_small_medium",
        "scope_decision": (
            "plan B: units reserving < %.0f GiB run now; the %d units reserving "
            ">= %.0f GiB are stage 2 and are started only by a human decision"
            % (STAGE1_MAX_RESERVE_GB, len(stage2), STAGE1_MAX_RESERVE_GB)),
        "pending": [u["unit"] for u in stage1],
        "claimed": {},
        "done": {u["unit"]: u["previous_status"] for u in kept},
        "units": {u["unit"]: u for u in stage1},
        "stage2_deferred": [
            {"unit": u["unit"], "reserve_gb": u["reserve_gb"],
             "est_peak_gb": u["est_peak_gb"], "out_numel": u["out_numel"],
             "est_wall_s_fast": u["est_wall_s_fast"],
             "est_wall_s_slow": u["est_wall_s_slow"]} for u in stage2],
    }, indent=2), encoding="utf-8")
    log("stage-1 queue written: %d pending, %d already done, %d deferred to "
        "stage 2 (requeued=%d fresh=%d in the full queue)"
        % (len(stage1), len(kept), len(stage2), len(requeued), len(fresh)))
    for lanes in (1, 2):
        fast = prep.simulate(stage1, lanes, BUDGET_GB, "est_wall_s_fast")
        slow = prep.simulate(stage1, lanes, BUDGET_GB, "est_wall_s_slow")
        log("stage-1 ETA %d lane(s): %.1f h .. %.1f h (model bracket; the upper "
            "end is an extrapolation)" % (lanes, fast / 3600, slow / 3600))
    return stage1, stage2


def precheck():
    result = subprocess.run([PY, str(MK / "_b9_precheck.py"),
                             "--budget-gb", "%d" % BUDGET_GB],
                            capture_output=True, text=True, cwd=str(MK),
                            timeout=900)
    return result.returncode, result.stdout + result.stderr


def fire_stage1(brake):
    current, _foreign = brake.sync()
    if current:
        log("a brake is held (%s); stage 1 waits" % brake_summary(brake))
        return False
    apps = brake.gpu_compute_apps()
    if apps:
        log("GPU compute app present, stage 1 waits: %s" % "; ".join(apps))
        return False
    code, output = precheck()
    if code != 0:
        for line in output.splitlines():
            if "[FAIL]" in line:
                log("precheck| " + line.strip())
        log("precheck refused (exit %d); will retry" % code)
        return False
    stage1, stage2 = build_stage1_queue()
    if not stage1:
        log("stage 1 has nothing left to run")
        STAGE1_DONE.write_text("nothing-to-run %s\n"
                               % time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                               encoding="utf-8")
        return None
    pid = start_guard(brake)
    STAGE1_FIRED.write_text(json.dumps({
        "fired_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "guard_pid": pid, "lanes": LANES, "budget_gb": BUDGET_GB,
        "stage1_units": len(stage1), "stage2_deferred_units": len(stage2),
        "note": ("stage 2 (>= %.0f GiB reservation) is deliberately not started; "
                 "its measured memory profile is the input to a human decision"
                 % STAGE1_MAX_RESERVE_GB),
    }, indent=2), encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# main loops
# ---------------------------------------------------------------------------

def wait_for_wave(brake, duty, label):
    """Poll until the queue in force has drained, keeping the run supervised."""
    announced = None
    while True:
        duty.poll()
        keep_guard_alive(brake)
        units = wave_units()
        rows = v2_rows()
        drivers = brake.find_processes("calib_driver_v2.py")
        guards = brake.find_processes("guard_b9")
        missing = [] if units is None else [u for u in units if u not in rows]
        drained = wave_drained()
        state = (len(units) if units else None, len(rows), bool(drivers),
                 bool(guards), drained, brake_summary(brake))
        if state != announced:
            log("%s: units=%s rows=%d lanes=%d guard=%d drained=%s brake=%s "
                "missing=%s" % (label, len(units) if units else None, len(rows),
                                len(drivers), len(guards), drained,
                                brake_summary(brake), missing[:5]))
            announced = state
        if units and drained and not missing and not drivers and not guards:
            log("%s complete: %d units, %d v2 rows, queue drained, no lane and "
                "no guard alive" % (label, len(units), len(rows)))
            return units, rows
        time.sleep(POLL_S)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK, "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("another supervisor holds %s -> exit (idempotent)" % LOCK.name)
        return 0
    handle.seek(0)
    handle.truncate()
    handle.write("%d\n" % os.getpid())
    handle.flush()

    log("=== supervisor start pid=%d lanes=%d budget=%.0fGiB poll=%ds ==="
        % (os.getpid(), LANES, BUDGET_GB, POLL_S))
    brake = _import("_b9_brake")
    duty = BrakeDuty(brake)
    log("brake state at startup: %s" % brake_summary(brake))
    if BLOCKED.is_file():
        log("STAGE1_BLOCKED present -> a human must clear it; brake duty only")
        while True:
            duty.poll()
            time.sleep(POLL_S)

    if not STAGE1_FIRED.is_file():
        units, rows = wait_for_wave(brake, duty, "first wave")
        report = evaluate_gate(units, rows)
        for detail in report["per_unit"]:
            log("wave1 %-22s %-30s exit=%-4s tol=%-12s est=%5.1fGB "
                "peak=%5.1fGB ratio=%s wall=%ss"
                % (detail["unit"], detail["status"], detail["exit_code"],
                   detail["calibrated_tol"], detail["est_peak_gb"],
                   detail["unit_peak_rss_gb"], detail["peak_over_estimate"],
                   detail["wall_s"]))
        if not report["passed"]:
            for reason in report["blockers"]:
                log("GATE BLOCKED: " + reason)
            BLOCKED.write_text(json.dumps({
                "blocked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "blockers": report["blockers"], "report": str(GATE_REPORT),
                "note": ("stage 1 was NOT started; the queue is untouched and a "
                         "human decides.  Delete this marker to re-arm."),
            }, indent=2), encoding="utf-8")
            log("stage 1 not started; STAGE1_BLOCKED written")
            while True:
                duty.poll()
                time.sleep(POLL_S)
        log("gate PASSED on all %d first-wave units" % report["units"])
        while True:
            outcome = fire_stage1(brake)
            if outcome is None:
                return 0
            if outcome:
                break
            duty.poll()
            time.sleep(POLL_S)
    else:
        log("STAGE1_FIRED present -> supervising the existing stage 1")

    wait_for_wave(brake, duty, "stage 1")
    counts = queue_state() or {}
    STAGE1_DONE.write_text(json.dumps({
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pending_left": len(counts.get("pending", [])),
        "next_step": ("stage 2 (the >= %.0f GiB units in "
                      "queue_state.json:stage2_deferred) is NOT started by this "
                      "supervisor; report the measured memory profile and wait "
                      "for a human decision" % STAGE1_MAX_RESERVE_GB),
    }, indent=2), encoding="utf-8")
    log("stage 1 finished; stage 2 left for a human decision")
    while True:
        duty.poll()
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
