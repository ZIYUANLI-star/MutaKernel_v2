#!/usr/bin/env python3
"""Wave-1.5 Lane P: batch-drive B7/B8/B9 ports and B11 over frozen subjects.

Per (subject, baseline): freeze the per-subject plan via run_e3_external.py
``plan`` (CPU), then execute it in an isolated subprocess via ``run`` (GPU).
Subprocess isolation mirrors the FSE worker discipline: an async CUDA crash
from one LLM-generated candidate must not poison later subjects.

B9: calibrated per-(task,dtype) absolute tolerances are injected into the
frozen plan's case parameters (field ``calibrated_tol``; PlanRunner consumes
it, falling back to the documented defaults).  The injection is recorded in
the plan under ``tolerance_injection``.

B11: a minimal replay driver (load candidate, one forward pass on template
inputs) is generated per subject and run under all four sanitizer tools.

Resume: a subject/baseline is skipped when its summary file exists.
Metering: wall seconds per subject/baseline land in the batch ledger
(Table 8 port cost columns).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

MK_ROOT = Path("/root/mk_v2")
PYBIN = "/root/miniconda3/bin/python"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(msg: str) -> None:
    print(f"[{_now()}] {msg}", flush=True)


def _load_manifest(path: Path) -> list:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return sorted(manifest["subjects"], key=lambda s: s["subject_id"])


def _artifact(root: Path, artifact: dict) -> Path:
    return root / artifact["logical_path"].lstrip("/")


def _contract_dtypes(contract: dict) -> list:
    dtypes = []
    for item in contract.get("tensor_inputs", []):
        for dt in item.get("dtypes", []):
            if dt not in dtypes:
                dtypes.append(dt)
    return dtypes


def _b7_backward(contract: dict) -> bool:
    execution = contract.get("execution", {})
    return bool(execution.get("backward")) and "train" in (
        execution.get("modes") or [])


def _inject_b9_tol(plan_path: Path, task_id: str, tol_map: dict) -> dict:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    injected, missing = [], []
    for case in plan["cases"]:
        dtype = case.get("parameters", {}).get("dtype", "float32")
        unit = f"{task_id}__{dtype}"
        tol = tol_map.get(unit)
        if tol is None:
            missing.append(unit)
            continue
        case["parameters"]["calibrated_tol"] = tol
        injected.append(unit)
    plan["tolerance_injection"] = {
        "source": "b9 calibration ledger (latest finished_at wins)",
        "injected_units": sorted(set(injected)),
        "missing_units_fallback_default": sorted(set(missing)),
    }
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan["tolerance_injection"]


B11_REPLAY_TEMPLATE = '''\
"""Auto-generated B11 replay driver: one forward pass of the candidate."""
import importlib.util
import sys

import torch


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


task = load({task_path!r}, "b11_task")
candidate = load({candidate_path!r}, "b11_candidate")

cls = getattr(candidate, "ModelNew", None) or getattr(candidate, "Model")
init = getattr(task, "get_init_inputs", None)
init_args = list(init()) if init else []
torch.manual_seed(42)
model = cls(*init_args).to("cuda").eval()
torch.manual_seed(0)
inputs = task.get_inputs()
if not isinstance(inputs, (list, tuple)):
    inputs = [inputs]
inputs = [v.to("cuda") if isinstance(v, torch.Tensor) else v for v in inputs]
with torch.no_grad():
    out = model(*inputs)
torch.cuda.synchronize()
print("B11_REPLAY_OK", out.shape if isinstance(out, torch.Tensor) else type(out))
'''


def run_ports(args):
    subjects = _load_manifest(args.subjects)
    if args.subject_ids:
        wanted = {
            line.strip()
            for line in Path(args.subject_ids).read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        subjects = [s for s in subjects if s["subject_id"] in wanted]
    artifact_root = Path(args.artifact_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plans_dir = out_dir / "plans"
    plans_dir.mkdir(exist_ok=True)
    ledger = out_dir / f"{args.baseline}_batch_ledger.jsonl"

    tol_map = {}
    if args.baseline == "b9" and args.b9_tol_map:
        payload = json.loads(Path(args.b9_tol_map).read_text(encoding="utf-8"))
        tol_map = payload.get("map", payload)

    script = MK_ROOT / "scripts" / "run_e3_external.py"
    done = skipped = failed = 0
    for subject in subjects:
        sid = subject["subject_id"]
        summary_path = out_dir / f"{args.baseline}_{sid}_summary.json"
        if summary_path.exists():
            skipped += 1
            continue

        task_path = _artifact(artifact_root, subject["reference"])
        candidate_path = _artifact(artifact_root, subject["candidate"])
        plan_path = plans_dir / f"{args.baseline}_{sid}.json"
        record = {
            "subject_id": sid,
            "baseline": args.baseline,
            "task_id": subject["task_id"],
            "dataset": subject["dataset"],
            "started_at": _now(),
        }
        t0 = time.time()
        try:
            if not plan_path.exists():
                plan_cmd = [
                    PYBIN, str(script), "plan",
                    "--baseline", args.baseline,
                    "--subject-id", sid,
                    "--out", str(plan_path),
                ]
                if args.baseline == "b7" and _b7_backward(subject["contract"]):
                    plan_cmd.append("--backward")
                if args.baseline == "b9":
                    declared = _contract_dtypes(subject["contract"])
                    usable = [d for d in declared if d in ("float32", "float16")]
                    plan_cmd += ["--b9-dtypes", *(usable or ["float32"])]
                subprocess.run(plan_cmd, check=True, capture_output=True,
                               text=True, timeout=300, cwd=str(MK_ROOT))
                if args.baseline == "b9" and tol_map:
                    record["tolerance_injection"] = _inject_b9_tol(
                        plan_path, subject["task_id"], tol_map)

            run_cmd = [
                PYBIN, str(script), "run",
                "--plan", str(plan_path),
                "--task-module", str(task_path),
                "--candidate-module", str(candidate_path),
                "--device", args.device,
                "--out-dir", str(out_dir),
            ]
            if args.device != "cpu":
                run_cmd.append("--allow-gpu")
            proc = subprocess.run(run_cmd, capture_output=True, text=True,
                                  timeout=args.timeout, cwd=str(MK_ROOT))
            record["exit_code"] = proc.returncode
            record["stderr_tail"] = proc.stderr[-2000:] if proc.returncode else ""
            if proc.returncode == 0 and summary_path.exists():
                record["status"] = "ok"
                done += 1
            else:
                record["status"] = "run_error"
                failed += 1
        except subprocess.TimeoutExpired:
            record["status"] = "timeout"
            failed += 1
        except Exception as exc:  # noqa: BLE001 — ledgered, never silent
            record["status"] = "driver_error"
            record["error"] = repr(exc)[:500]
            failed += 1
        record["wall_s"] = round(time.time() - t0, 2)
        record["finished_at"] = _now()
        with open(ledger, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
        _log(f"{args.baseline} {sid}: {record['status']} ({record['wall_s']}s) "
             f"[done={done} skip={skipped} fail={failed}]")

    _log(f"{args.baseline} batch complete: done={done} resumed_skip={skipped} "
         f"failed={failed}")
    print(json.dumps({"baseline": args.baseline, "done": done,
                      "skipped": skipped, "failed": failed}))


def run_b11(args):
    subjects = _load_manifest(args.subjects)
    if args.subject_ids:
        wanted = {
            line.strip()
            for line in Path(args.subject_ids).read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        subjects = [s for s in subjects if s["subject_id"] in wanted]
    artifact_root = Path(args.artifact_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    drivers_dir = out_dir / "replay_drivers"
    drivers_dir.mkdir(exist_ok=True)
    ledger = out_dir / "b11_batch_ledger.jsonl"
    script = MK_ROOT / "scripts" / "b11_compute_sanitizer.py"

    done = skipped = failed = 0
    for subject in subjects:
        sid = subject["subject_id"]
        result_path = out_dir / sid / "b11_result.json"
        if result_path.exists():
            skipped += 1
            continue
        driver_path = drivers_dir / f"{sid}.py"
        driver_path.write_text(
            B11_REPLAY_TEMPLATE.format(
                task_path=str(_artifact(artifact_root, subject["reference"])),
                candidate_path=str(_artifact(artifact_root, subject["candidate"])),
            ),
            encoding="utf-8",
        )
        record = {"subject_id": sid, "started_at": _now()}
        t0 = time.time()
        try:
            proc = subprocess.run(
                [PYBIN, str(script), "--subject-id", sid,
                 "--out-dir", str(out_dir),
                 "--timeout", str(args.tool_timeout),
                 "--", PYBIN, str(driver_path)],
                capture_output=True, text=True, timeout=args.timeout,
                cwd=str(MK_ROOT),
            )
            record["exit_code"] = proc.returncode
            if proc.returncode == 0 and result_path.exists():
                record["status"] = "ok"
                done += 1
            else:
                record["status"] = "run_error"
                record["stderr_tail"] = proc.stderr[-2000:]
                failed += 1
        except subprocess.TimeoutExpired:
            record["status"] = "timeout"
            failed += 1
        except Exception as exc:  # noqa: BLE001
            record["status"] = "driver_error"
            record["error"] = repr(exc)[:500]
            failed += 1
        record["wall_s"] = round(time.time() - t0, 2)
        record["finished_at"] = _now()
        with open(ledger, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
        _log(f"b11 {sid}: {record['status']} ({record['wall_s']}s) "
             f"[done={done} skip={skipped} fail={failed}]")

    _log(f"b11 batch complete: done={done} resumed_skip={skipped} failed={failed}")
    print(json.dumps({"baseline": "b11", "done": done, "skipped": skipped,
                      "failed": failed}))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", required=True,
                    choices=["b7", "b8", "b9", "b11"])
    ap.add_argument("--subjects", required=True, type=Path)
    ap.add_argument("--subject-ids", type=Path)
    ap.add_argument("--artifact-root", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--timeout", type=int, default=1800,
                    help="per-subject wall timeout (s)")
    ap.add_argument("--tool-timeout", type=int, default=600,
                    help="B11 per-sanitizer-tool timeout (s)")
    ap.add_argument("--b9-tol-map", type=Path)
    args = ap.parse_args()
    if args.baseline == "b11":
        run_b11(args)
    else:
        run_ports(args)


if __name__ == "__main__":
    main()
