#!/usr/bin/env python3
"""B9 calibration prep (one-shot, remote): build task_table.json (200 KB
L1+L2 tasks from the C2/C3/C5 contract draft, reduction-heavy first) and
run_manifest.json (environment fingerprint).  Read-only w.r.t. E1 data."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

MK = Path("/root/mk_v2")
RUNS = Path("/root/mk_v2_runs")
OUT = RUNS / "e3_b9_calib"
DRAFT = RUNS / "e2_reconcile" / "contracts_c2c3c5_draft.jsonl"
KB_ROOT = MK / "KernelBench" / "KernelBench"
CALIBRATED_SET = ("float32", "float16")
TASK_RE = re.compile(r"^(?:KB_)?L(\d)_P(\d+)$")

# Ordering heuristic only (which units run first) - never touches judging.
REDUCTION_KEYWORDS = (
    "matmul", "matrix_mult", "gemm", "bmm", "einsum", "softmax", "norm",
    "sum", "mean", "prod", "cum", "argmax", "argmin", "logsumexp", "pool",
    "conv", "attention", "cosine", "dot", "mse", "loss", "cross_entropy",
    "kl_div", "hinge", "triplet", "std", "var", "reduction", "gram", "scan",
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tasks, gaps = [], []
    draft_bytes = DRAFT.read_bytes()
    for line in draft_bytes.decode("utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        task_id = row["task_id"]
        match = TASK_RE.match(task_id)
        if not match:
            gaps.append({"task": task_id, "reason": "non-KB task key"})
            continue
        level, problem = int(match.group(1)), int(match.group(2))
        hits = sorted((KB_ROOT / f"level{level}").glob(f"{problem}_*.py"))
        if len(hits) != 1:
            gaps.append({"task": task_id,
                         "reason": f"problem file hits={len(hits)}"})
            continue
        float_dtypes = set()
        for tensor_input in row["contract"]["tensor_inputs"]:
            for dtype in tensor_input.get("dtypes", []):
                if dtype in CALIBRATED_SET:
                    float_dtypes.add(dtype)
        dtypes = [d for d in CALIBRATED_SET if d in float_dtypes] or ["float32"]
        name = hits[0].name.lower()
        tasks.append({
            "task_key": task_id,
            "file": str(hits[0].relative_to(MK)),
            "level": level,
            "dtypes": dtypes,
            "reduction_heavy": any(k in name for k in REDUCTION_KEYWORDS),
        })
    tasks.sort(key=lambda t: (not t["reduction_heavy"], t["level"],
                              int(TASK_RE.match(t["task_key"]).group(2))))

    n_units = sum(len(t["dtypes"]) for t in tasks)
    table = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_contract_draft": str(DRAFT),
        "source_sha256": hashlib.sha256(draft_bytes).hexdigest(),
        "n_tasks": len(tasks),
        "n_units": n_units,
        "n_reduction_heavy": sum(t["reduction_heavy"] for t in tasks),
        "gaps": gaps,
        "tasks": tasks,
    }
    (OUT / "task_table.json").write_text(json.dumps(table, indent=2),
                                         encoding="utf-8")

    def sh(cmd):
        try:
            return subprocess.run(cmd, shell=True, capture_output=True,
                                  text=True, timeout=60).stdout.strip()
        except Exception as exc:
            return f"ERR {exc}"

    import torch
    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "purpose": ("E3 pre-flight: B9 per-(subject,dtype) control "
                    "calibration on unmutated reference kernels"),
        "protocol": {
            "controls_per_unit": 32,
            "seeds": "0..31 (plan_b9_port, single dtype per plan)",
            "candidate": "reference task module itself (unmutated control)",
            "candidate_device": "cuda (A800)",
            "reference": "fp64 CPU (run_fp64_cpu_reference)",
            "tolerance_rule": "p95 of control max-abs errors x 1.5 "
                              "(calibrate_tolerance, unchanged port code)",
            "harness": "scripts/run_e3_external.py plan/run (unchanged)",
        },
        "env": {
            "hostname": sh("hostname"),
            "gpu": sh("nvidia-smi --query-gpu=name,driver_version,memory.total "
                      "--format=csv,noheader"),
            "python": sh("/root/miniconda3/bin/python --version"),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "git_head": sh("cd /root/mk_v2 && git log -1 --format=%H 2>/dev/null"),
            "nproc": sh("nproc"),
        },
        "layout": {
            "lanes": 4,
            "checkpoint": "completed_lane{N}.json (E1 pattern)",
            "calibration_rows": "calibration_lane{N}.jsonl",
            "units_dir": "units/<task_key>__<dtype>/",
            "guard": "guard_b9.sh (restart dead lanes, log, cap 20)",
        },
        "e1_data": "read-only, untouched",
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2),
                                           encoding="utf-8")
    print(json.dumps({
        "tasks": len(tasks), "units": n_units,
        "reduction_heavy": table["n_reduction_heavy"],
        "gaps": gaps,
        "first10": [t["task_key"] for t in tasks[:10]],
    }, indent=2))
    print("B9_PREP_DONE")


if __name__ == "__main__":
    main()
