"""Remote-side: split lane0's REMAINING kernels into lanes 2/3 (plan v2).

Per-kernel time estimate: lane0's measured per-kernel median wall if
available, else plan-v1 per_probe_s scaled by the measured/planned
calibration factor over lane0-observed kernels.  Pure greedy balance (both
new lanes carry heavy subjects by design; user authorised dual-heavy
concurrency under MK_GPU_MEMORY_FRACTION=0.45 caps).

Appends lanes[2]/lanes[3] to lane_plan.json; lanes 0/1 entries untouched.
Asserts: lane2/3 disjoint and their union == lane0 remaining kernel set.
"""
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/mk_v2")
from scripts.run_e1_probe_study import plan_equiv_lanes  # noqa: E402

E1 = Path("/root/mk_v2_runs/e1")
plan_path = E1 / "lane_plan.json"
plan = json.loads(plan_path.read_text(encoding="utf-8"))
if len(plan["lanes"]) != 2:
    raise SystemExit(f"REFUSE: expected 2 lanes in plan, got {len(plan['lanes'])}")

completed = set(json.load(open(E1 / "equiv_completed.json")))
for lane_file in sorted(E1.glob("equiv_completed_lane*.json")):
    completed |= set(json.load(open(lane_file)))

survivors_by_kernel = {}
with open(E1 / "baseline_observations.jsonl", encoding="utf-8") as fh:
    for line in fh:
        row = json.loads(line)
        if row.get("status") == "survived":
            survivors_by_kernel.setdefault(row["kernel"], []).append(row["probe_id"])

lane0_kernels = plan["lanes"][0]["kernels"]
remaining = {}
for kernel in lane0_kernels:
    left = [p for p in survivors_by_kernel.get(kernel, []) if p not in completed]
    if left:
        remaining[kernel] = len(left)

walls = {}
obs0 = E1 / "equiv_observations_lane0.jsonl"
for line in open(obs0, encoding="utf-8"):
    row = json.loads(line)
    walls.setdefault(row["kernel"], []).append(row["wall_ms"] / 1000)
measured = {k: statistics.median(v) for k, v in walls.items()}

per = plan["per_kernel"]
factors = [measured[k] / max(1.0, per[k]["per_probe_s"])
           for k in measured if k in per]
calib = statistics.median(factors) if factors else 1.0
print(f"calibration factor over {len(factors)} lane0 kernels: {calib:.2f}")

loads, per_probe = {}, {}
for kernel, count in remaining.items():
    est = measured.get(kernel)
    if est is None:
        est = min(900.0, per[kernel]["per_probe_s"] * calib)
    per_probe[kernel] = round(est, 1)
    loads[kernel] = est * count

split, totals = plan_equiv_lanes(loads, heavy_kernels=[], n_lanes=2)
assert not (set(split[0]) & set(split[1]))
assert set(split[0]) | set(split[1]) == set(remaining)

for i, kernels in enumerate(split):
    lane_id = 2 + i
    plan["lanes"].append({
        "lane": lane_id,
        "kernels": kernels,
        "kernel_count": len(kernels),
        "probe_count": sum(remaining[k] for k in kernels),
        "est_seconds": round(totals[i], 1),
        "est_hours": round(totals[i] / 3600, 2),
        "split_from": 0,
        "per_probe_s": {k: per_probe[k] for k in kernels},
    })
plan["version"] = 2
plan["v2_created_at"] = datetime.now(timezone.utc).isoformat()
plan["v2_note"] = ("lanes 2/3 split lane0's remaining kernels after lane1 "
                   "finished (2026-07-24 22:53 +0800); lanes 0/1 retired")
plan_path.write_text(json.dumps(plan, indent=1), encoding="utf-8")

for entry in plan["lanes"][2:]:
    print(f"lane {entry['lane']}: kernels={entry['kernel_count']} "
          f"probes={entry['probe_count']} est={entry['est_hours']}h "
          f"-> {entry['kernels']}")
print("LANE_PLAN_V2_OK")
