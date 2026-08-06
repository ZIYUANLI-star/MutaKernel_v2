"""Remote-side (CPU-only): estimate per-kernel load and write lane_plan.json.

Heavy lane rule: a kernel is heavy if (a) it had 420s-timeout probes in the
archived v1 records, (b) its estimated per-probe time >= 600s, or (c) its
estimated peak VRAM > 20GB (get_inputs bytes x factor 6).  All heavy kernels
are pinned to lane 0 by plan_equiv_lanes.

Run with CUDA_VISIBLE_DEVICES= so nothing touches the GPU.
"""
import gc
import importlib.util
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/mk_v2")
from scripts.run_e1_probe_study import plan_equiv_lanes  # noqa: E402

E1 = Path("/root/mk_v2_runs/e1")
KB_ROOT = Path("/root/mk_v2/KernelBench")
HEAVY_TIME_S = 600.0
HEAVY_MEM_GB = 20.0
MEM_FACTOR = 6.0  # inputs on device + ref/cand outputs + clone_tree copies
TIMEOUT_KERNEL_EST_S = 800.0  # observed 697-816s under the 900s budget


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


baseline = read_jsonl(E1 / "baseline_observations.jsonl")
completed = set(json.loads((E1 / "equiv_completed.json").read_text()))

surv_by_kernel, base_wall = {}, {}
for r in baseline:
    if r.get("status") != "survived":
        continue
    surv_by_kernel.setdefault(r["kernel"], []).append(r["probe_id"])
    if r.get("wall_ms"):
        base_wall.setdefault(r["kernel"], []).append(r["wall_ms"] / 1000)

eq_wall = {}
for r in read_jsonl(E1 / "equiv_observations.jsonl"):
    eq_wall.setdefault(r["kernel"], []).append(r["wall_ms"] / 1000)
timeout_kernels = {
    r["kernel"] for r in read_jsonl(E1 / "equiv_observations_timeout_v1.jsonl")}

ratios = [
    statistics.median(walls) / max(1e-6, statistics.median(base_wall[k]))
    for k, walls in eq_wall.items()
    if k not in timeout_kernels and k in base_wall
]
ratio = statistics.median(ratios) if ratios else 6.0
print(f"equiv/baseline wall ratio (median over {len(ratios)} kernels): {ratio:.2f}")


def per_probe_s(kernel):
    if kernel in timeout_kernels:
        return TIMEOUT_KERNEL_EST_S
    if kernel in eq_wall:
        return min(900.0, statistics.median(eq_wall[kernel]))
    if kernel in base_wall:
        return min(900.0, max(60.0, ratio * statistics.median(base_wall[kernel])))
    return 300.0


def input_gb(kernel):
    import torch
    try:
        meta = json.loads((E1 / "probes" / f"{kernel}.json").read_text())["kernel"]
        level_dir = KB_ROOT / "KernelBench" / f"level{meta['level']}"
        matches = sorted(level_dir.glob(f"{meta['problem_id']}_*.py"))
        spec = importlib.util.spec_from_file_location(f"plan_{kernel}", matches[0])
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        torch.manual_seed(0)
        values = mod.get_inputs()
        if not isinstance(values, (list, tuple)):
            values = [values]
        n_bytes = sum(v.numel() * v.element_size()
                      for v in values if hasattr(v, "numel"))
        del values
        gc.collect()
        return n_bytes / 2 ** 30
    except Exception as exc:
        print("MEM_EST_FAIL", kernel, type(exc).__name__, str(exc)[:120])
        return None


remaining = {
    k: [pid for pid in pids if pid not in completed]
    for k, pids in surv_by_kernel.items()
}
loads, per_kernel = {}, {}
heavy = set()
for kernel, pids in sorted(remaining.items()):
    if not pids:
        continue
    est = per_probe_s(kernel)
    gb_in = input_gb(kernel)
    peak_gb = None if gb_in is None else gb_in * MEM_FACTOR
    is_heavy = (
        kernel in timeout_kernels
        or est >= HEAVY_TIME_S
        or (peak_gb is not None and peak_gb > HEAVY_MEM_GB)
    )
    if is_heavy:
        heavy.add(kernel)
    loads[kernel] = est * len(pids)
    per_kernel[kernel] = {
        "remaining_probes": len(pids),
        "per_probe_s": round(est, 1),
        "input_gb": None if gb_in is None else round(gb_in, 3),
        "est_peak_gb": None if peak_gb is None else round(peak_gb, 2),
        "heavy": is_heavy,
        "timeout_kernel": kernel in timeout_kernels,
    }

lanes, totals = plan_equiv_lanes(loads, heavy)
plan = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "criteria": {
        "heavy_time_s": HEAVY_TIME_S,
        "heavy_mem_gb": HEAVY_MEM_GB,
        "mem_factor": MEM_FACTOR,
        "timeout_kernel_est_s": TIMEOUT_KERNEL_EST_S,
        "equiv_over_baseline_ratio": round(ratio, 3),
    },
    "heavy_kernels": sorted(heavy),
    "lanes": [
        {
            "lane": i,
            "kernels": lanes[i],
            "kernel_count": len(lanes[i]),
            "probe_count": sum(len(remaining[k]) for k in lanes[i]),
            "est_seconds": round(totals[i], 1),
            "est_hours": round(totals[i] / 3600, 2),
        }
        for i in range(len(lanes))
    ],
    "per_kernel": per_kernel,
}
(E1 / "lane_plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")

for entry in plan["lanes"]:
    print(f"lane {entry['lane']}: kernels={entry['kernel_count']} "
          f"probes={entry['probe_count']} est={entry['est_hours']}h")
print("heavy kernels:", ",".join(sorted(heavy)))
print("LANE_PLAN_OK")
