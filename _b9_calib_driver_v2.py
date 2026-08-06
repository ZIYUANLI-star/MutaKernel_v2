#!/usr/bin/env python3
"""B9 control-calibration lane driver v2 (resume after the quantile fix).

Deployed to /root/mk_v2/_b9_calib_driver_v2.py.  Each unit is still executed
with exactly the v1 command line (`run_e3_external.py plan` then `run --device
cuda --allow-gpu`) and the rows keep v1's field names and meanings, so the 18
rows carried over from the 16:38 run stay comparable with everything produced
here.  What changed is scheduling, not grading:

  * one global work queue (queue_state.json, flock'd) instead of a fixed
    ``index % lanes`` shard, so a unit completed in any wave by any lane is
    never repeated and the lane count may change between waves;
  * an explicit host-memory budget.  A unit reserves its estimated peak
    (unit_size_table.json x safety factor) before it starts and waits until the
    reservation fits, which serialises the units whose fp64 reference plus
    error statistics need 50-84GB.  This is what the 4-lane run got wrong: it
    ran four such units at once under a 120GiB cap and the kernel OOM-killed
    both a B9 unit and the critical-path CSE worker;
  * PAUSED_FOR_SIGNOFF_RERUN is honoured between units -- the lane finishes the
    unit in flight, records it, and exits cleanly, and the guard will not
    restart it while the marker exists;
  * a unit is refused while a critical-path _mutant_worker.py is alive.

Stale claims (a lane killed mid-unit) are detected by pid liveness and returned
to the queue, so kill/restart still resumes at unit granularity.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

MK = Path("/root/mk_v2")
PY = "/root/miniconda3/bin/python"
CRITICAL_PATH_NEEDLE = "_mutant_worker.py"
# v1 ran with 24 intra-op threads; keep it so wall times stay comparable (the
# fp64 reductions themselves are thread-count invariant, verified separately)
UNIT_THREADS = "24"
ADMISSION_POLL_S = 20
GIB = float(1 << 30)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def log(message: str) -> None:
    print(f"[b9-cal-v2 {now()}] {message}", flush=True)


@contextmanager
def locked(path: Path):
    handle = open(str(path) + ".lock", "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


def load_state(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state) -> None:
    tmp = str(path) + ".tmp"
    Path(tmp).write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def pid_alive(pid: int) -> bool:
    return Path(f"/proc/{pid}").is_dir()


def _ppid(pid: int) -> int:
    try:
        for line in open(f"/proc/{pid}/status", encoding="utf-8"):
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def find_processes(needle: str):
    """/proc scan excluding self and ancestors -- never `pkill -f`."""
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
            raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        except OSError:
            continue
        if needle in raw.replace(b"\0", b" ").decode("utf-8", "replace"):
            hits.append(pid)
    return hits


def peak_rss_gb(pid: int) -> float:
    try:
        for line in open(f"/proc/{pid}/status", encoding="utf-8"):
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) / 1048576.0
    except OSError:
        pass
    return 0.0


# ---------------------------------------------------------------------------
# queue + memory admission
# ---------------------------------------------------------------------------

def claim_unit(state_path: Path, lane: int, budget_gb: float):
    """First-fit claim: the first pending unit whose reservation fits.

    Returns (unit, remaining_pending) or (None, remaining_pending) when nothing
    is admissible right now (a peer lane holds the budget).
    """
    with locked(state_path):
        state = load_state(state_path)
        for uid, claim in list(state["claimed"].items()):
            if not pid_alive(claim["pid"]):
                log(f"reclaiming {uid} from dead lane {claim['lane']} "
                    f"(pid {claim['pid']})")
                state["pending"].insert(0, uid)
                del state["claimed"][uid]
        reserved = sum(c["reserve_gb"] for c in state["claimed"].values())
        chosen = None
        for uid in state["pending"]:
            reserve = float(state["units"][uid]["reserve_gb"])
            if not state["claimed"] or reserved + reserve <= budget_gb:
                chosen = uid
                break
        if chosen is None:
            save_state(state_path, state)
            return None, len(state["pending"])
        state["pending"].remove(chosen)
        state["claimed"][chosen] = {
            "lane": lane, "pid": os.getpid(), "since": now(),
            "reserve_gb": float(state["units"][chosen]["reserve_gb"]),
        }
        save_state(state_path, state)
        return dict(state["units"][chosen]), len(state["pending"])


def release_unit(state_path: Path, uid: str, status: str) -> None:
    with locked(state_path):
        state = load_state(state_path)
        state["claimed"].pop(uid, None)
        state["done"][uid] = status
        save_state(state_path, state)


# ---------------------------------------------------------------------------
# unit execution (identical command lines and statuses to v1)
# ---------------------------------------------------------------------------

def summarize_observations(obs_path: Path):
    obs = [json.loads(line)
           for line in obs_path.read_text(encoding="utf-8").splitlines()
           if line.strip()]
    errors, kinds = [], {}
    for observation in obs:
        b9 = observation.get("b9")
        if observation["status"] == "PASS":
            kind = "pass"
        elif b9 is None:
            kind = "exec_fail" if observation["status"] == "FAIL" else "inconclusive"
        else:
            kind = b9.get("failure_kind") or "pass"
        kinds[kind] = kinds.get(kind, 0) + 1
        if b9 is not None and b9.get("failure_kind") in (None, "tolerance"):
            errors.append(float(b9["max_abs_err"]))
    return obs, errors, kinds


def run_watched(command, unit_dir: Path, timeout: int, env):
    """subprocess.run(timeout=...) semantics plus the child's peak RSS."""
    with open(unit_dir / "run.log", "wb") as log_file:
        process = subprocess.Popen(command, cwd=MK, stdout=log_file,
                                   stderr=subprocess.STDOUT, env=env)
        deadline = time.time() + timeout
        peak = 0.0
        while True:
            try:
                process.wait(timeout=5)
                break
            except subprocess.TimeoutExpired:
                peak = max(peak, peak_rss_gb(process.pid))
                if time.time() > deadline:
                    process.kill()
                    process.wait()
                    raise subprocess.TimeoutExpired(command, timeout)
    return process.returncode, round(peak, 2)


def run_unit(unit, unit_dir: Path, calibrate):
    row = {
        "unit": unit["unit"],
        "task_key": unit["task_key"],
        "dtype": unit["dtype"],
        "task_file": unit["task_file"],
        "reduction_heavy": unit["reduction_heavy"],
        "started_at": now(),
        "wave": "v2_post_quantile_fix",
        "est_peak_gb": unit["est_peak_gb"],
        "unit_timeout_s": unit["unit_timeout_s"],
    }
    started = time.time()
    plan_path = unit_dir / "plan.json"
    try:
        subprocess.run(
            [PY, "scripts/run_e3_external.py", "plan", "--baseline", "b9",
             "--subject-id", unit["task_key"], "--b9-dtypes", unit["dtype"],
             "--out", str(plan_path)],
            cwd=MK, check=True, capture_output=True, timeout=300)
        code, peak = run_watched(
            [PY, "scripts/run_e3_external.py", "run",
             "--plan", str(plan_path),
             "--task-module", unit["task_file"],
             "--candidate-module", unit["task_file"],
             "--device", "cuda", "--allow-gpu",
             "--out-dir", str(unit_dir)],
            unit_dir, unit["unit_timeout_s"],
            {**os.environ, "CUDA_VISIBLE_DEVICES": "0",
             "OMP_NUM_THREADS": UNIT_THREADS, "MKL_NUM_THREADS": UNIT_THREADS})
        row["exit_code"] = code
        row["unit_peak_rss_gb"] = peak
        if code != 0:
            row["control_status"] = "run_error"
        else:
            obs_path = unit_dir / f"b9_{unit['task_key']}_observations.jsonl"
            obs, errors, kinds = summarize_observations(obs_path)
            row["cases"] = len(obs)
            row["outcome_kinds"] = kinds
            row["n_control_errors"] = len(errors)
            if len(errors) == len(obs) == 32:
                tol = calibrate(errors)
                row["calibrated_tol"] = tol
                row["control_max_abs"] = max(errors)
                row["control_pass_rate_at_tol"] = (
                    sum(1 for error in errors if error <= tol) / 32.0)
                row["control_status"] = ("calibrated_ok" if max(errors) <= tol
                                         else "calibrated_heavy_tail")
            else:
                row["control_status"] = "controls_incomplete"
    except subprocess.TimeoutExpired:
        row["control_status"] = "control_timeout"
    except Exception as exc:  # containment: record it, keep the lane alive
        row["control_status"] = "driver_exception"
        row["error"] = f"{type(exc).__name__}: {exc}"
    row["wall_s"] = round(time.time() - started, 1)
    row["finished_at"] = now()
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", type=int, required=True)
    parser.add_argument("--out-root", default="/root/mk_v2_runs/e3_b9_calib")
    parser.add_argument("--budget-gb", type=float, default=100.0)
    args = parser.parse_args()

    out_root = Path(args.out_root)
    state_path = out_root / "queue_state.json"
    pause_marker = out_root / "PAUSED_FOR_SIGNOFF_RERUN"
    if not state_path.is_file():
        raise SystemExit("queue_state.json missing - run _b9_resume_prep --commit")

    alive = find_processes(CRITICAL_PATH_NEEDLE)
    if alive:
        raise SystemExit(f"refusing to start: critical-path worker alive {alive}")

    sys.path.insert(0, str(MK))
    from src.experiments.external_ports import calibrate_tolerance

    calibration_path = out_root / f"calibration_v2_lane{args.lane}.jsonl"
    completed_path = out_root / f"completed_v2_lane{args.lane}.json"
    completed = []
    if completed_path.is_file():
        completed = json.loads(completed_path.read_text(encoding="utf-8"))
    log(f"lane {args.lane} up: budget {args.budget_gb:.0f} GiB, "
        f"{len(completed)} units done by this lane so far")

    while True:
        if pause_marker.is_file():
            log(f"{pause_marker.name} present -> lane {args.lane} stops "
                f"(guard will not restart while it exists)")
            return
        unit, remaining = claim_unit(state_path, args.lane, args.budget_gb)
        if unit is None:
            if remaining == 0:
                (out_root / f"B9_CALIB_V2_DONE_LANE{args.lane}").touch()
                log(f"queue drained; lane {args.lane} done "
                    f"({len(completed)} units this lane)")
                return
            log(f"{remaining} units pending but none fits the remaining budget; "
                f"waiting {ADMISSION_POLL_S}s")
            time.sleep(ADMISSION_POLL_S)
            continue

        unit_dir = out_root / "units" / unit["unit"]
        unit_dir.mkdir(parents=True, exist_ok=True)
        log(f"start {unit['unit']} (reserve {unit['reserve_gb']:.1f} GiB, "
            f"timeout {unit['unit_timeout_s']}s, {remaining} left)")
        row = run_unit(unit, unit_dir, calibrate_tolerance)
        row["lane"] = args.lane
        with open(calibration_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
        completed.append(unit["unit"])
        tmp = str(completed_path) + ".tmp"
        Path(tmp).write_text(json.dumps(sorted(completed), indent=2),
                             encoding="utf-8")
        os.replace(tmp, completed_path)
        release_unit(state_path, unit["unit"], row["control_status"])
        log(f"{unit['unit']}: {row['control_status']} "
            f"tol={row.get('calibrated_tol')} peak_rss={row.get('unit_peak_rss_gb')}GB "
            f"wall={row['wall_s']}s")


if __name__ == "__main__":
    main()
