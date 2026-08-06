#!/usr/bin/env python3
"""B9 control-calibration lane driver (E3 pre-flight; runtime skeleton only).

Deployed to /root/mk_v2/_b9_calib_driver.py.  For each (task, dtype) unit in
this lane's shard of task_table.json:

  1. freeze a 32-control-case plan (seeds 0..31, single dtype) via
     scripts/run_e3_external.py plan --baseline b9;
  2. execute it with candidate == the reference task module itself on the GPU
     (the fp64 reference side stays on CPU per protocol) via
     scripts/run_e3_external.py run --device cuda --allow-gpu;
  3. derive the per-(subject,dtype) calibrated tolerance with the port's own
     calibrate_tolerance (p95 of control max-abs errors x 1.5) and append one
     row to calibration_lane{N}.jsonl.

Grading semantics are NOT modified anywhere: this only drives the existing
harness and aggregates its observation files.  completed_lane{N}.json is the
E1-style checkpoint (kill/restart resumes at unit granularity).  Each unit
runs in its own subprocess so an OOM/crash/timeout is contained and recorded
as a control_* status instead of killing the lane.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

MK = Path("/root/mk_v2")
PY = "/root/miniconda3/bin/python"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def log(msg: str) -> None:
    print(f"[b9-cal {now()}] {msg}", flush=True)


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def atomic_write(path, obj) -> None:
    tmp = str(path) + ".tmp"
    Path(tmp).write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def summarize_observations(obs_path: Path):
    """Collect control outcome kinds + the finite max-abs error list."""
    obs = [json.loads(line)
           for line in obs_path.read_text(encoding="utf-8").splitlines()
           if line.strip()]
    errors, kinds = [], {}
    for o in obs:
        b9 = o.get("b9")
        if o["status"] == "PASS":
            kind = "pass"
        elif b9 is None:
            # candidate execution failed / non-tensor output / fp64 ref failed
            kind = "exec_fail" if o["status"] == "FAIL" else "inconclusive"
        else:
            kind = b9.get("failure_kind") or "pass"
        kinds[kind] = kinds.get(kind, 0) + 1
        if b9 is not None and b9.get("failure_kind") in (None, "tolerance"):
            errors.append(float(b9["max_abs_err"]))
    return obs, errors, kinds


def run_unit(task, dtype, unit_dir: Path, unit_timeout: int, calibrate):
    row = {
        "unit": f"{task['task_key']}__{dtype}",
        "task_key": task["task_key"],
        "dtype": dtype,
        "task_file": task["file"],
        "reduction_heavy": task["reduction_heavy"],
        "started_at": now(),
    }
    t0 = time.time()
    plan_path = unit_dir / "plan.json"
    try:
        subprocess.run(
            [PY, "scripts/run_e3_external.py", "plan", "--baseline", "b9",
             "--subject-id", task["task_key"], "--b9-dtypes", dtype,
             "--out", str(plan_path)],
            cwd=MK, check=True, capture_output=True, timeout=300)
        with open(unit_dir / "run.log", "wb") as lf:
            proc = subprocess.run(
                [PY, "scripts/run_e3_external.py", "run",
                 "--plan", str(plan_path),
                 "--task-module", task["file"],
                 "--candidate-module", task["file"],
                 "--device", "cuda", "--allow-gpu",
                 "--out-dir", str(unit_dir)],
                cwd=MK, stdout=lf, stderr=subprocess.STDOUT,
                timeout=unit_timeout,
                env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"})
        row["exit_code"] = proc.returncode
        if proc.returncode != 0:
            row["control_status"] = "run_error"
        else:
            obs_path = unit_dir / f"b9_{task['task_key']}_observations.jsonl"
            obs, errors, kinds = summarize_observations(obs_path)
            row["cases"] = len(obs)
            row["outcome_kinds"] = kinds
            row["n_control_errors"] = len(errors)
            if len(errors) == len(obs) == 32:
                tol = calibrate(errors)
                pass_rate = sum(1 for e in errors if e <= tol) / 32.0
                row["calibrated_tol"] = tol
                row["control_max_abs"] = max(errors)
                row["control_pass_rate_at_tol"] = pass_rate
                row["control_status"] = ("calibrated_ok"
                                         if max(errors) <= tol
                                         else "calibrated_heavy_tail")
            else:
                row["control_status"] = "controls_incomplete"
    except subprocess.TimeoutExpired:
        row["control_status"] = "control_timeout"
    except Exception as exc:  # containment: record, keep the lane alive
        row["control_status"] = "driver_exception"
        row["error"] = f"{type(exc).__name__}: {exc}"
    row["wall_s"] = round(time.time() - t0, 1)
    row["finished_at"] = now()
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", type=int, required=True)
    ap.add_argument("--lanes-total", type=int, required=True)
    ap.add_argument("--out-root", default="/root/mk_v2_runs/e3_b9_calib")
    ap.add_argument("--unit-timeout", type=int, default=3600)
    args = ap.parse_args()

    out_root = Path(args.out_root)
    table = load_json(out_root / "task_table.json", None)
    if not table:
        raise SystemExit("task_table.json missing - run _b9_calib_prep first")

    units = []
    for index, task in enumerate(table["tasks"]):
        if index % args.lanes_total != args.lane:
            continue
        for dtype in task["dtypes"]:
            units.append((task, dtype))

    completed_path = out_root / f"completed_lane{args.lane}.json"
    completed = set(load_json(completed_path, []))
    cal_path = out_root / f"calibration_lane{args.lane}.jsonl"
    log(f"lane {args.lane}/{args.lanes_total}: {len(units)} units, "
        f"{len(completed)} already completed")

    sys.path.insert(0, str(MK))
    from src.experiments.external_ports import calibrate_tolerance

    for task, dtype in units:
        uid = f"{task['task_key']}__{dtype}"
        if uid in completed:
            continue
        unit_dir = out_root / "units" / uid
        unit_dir.mkdir(parents=True, exist_ok=True)
        row = run_unit(task, dtype, unit_dir, args.unit_timeout,
                       calibrate_tolerance)
        with open(cal_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        completed.add(uid)
        atomic_write(completed_path, sorted(completed))
        log(f"{uid}: {row.get('control_status')} "
            f"tol={row.get('calibrated_tol')} wall={row['wall_s']}s")

    (out_root / f"B9_CALIB_DONE_LANE{args.lane}").touch()
    log(f"lane {args.lane} DONE ({len(completed)} units)")


if __name__ == "__main__":
    main()
