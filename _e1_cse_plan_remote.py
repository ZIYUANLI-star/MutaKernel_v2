"""Remote-side: per-kernel profile -> conservative heavy/light split ->
three-lane CSE plan (lane0 heavy serial, lanes 1/2 light balanced).

Heavy rule (conservative): timeout history OR resource-limit history OR
equiv wall median > 300s.  CSE per-probe estimate scales the equiv median
by the round-count ratio (103/32), capped at the 1800s probe budget.

Asserts: lanes disjoint; union == kernels of ALL LIKELY_EQUIVALENT probes.
Safe to re-run after the merge (it re-reads the LIKELY set each time).
"""
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/mk_v2")
from scripts.run_e1_probe_study import plan_equiv_lanes  # noqa: E402

E1 = Path("/root/mk_v2_runs/e1")
HEAVY_WALL_S = 300.0
CSE_ROUNDS_RATIO = (40 + 21 * 3) / 32.0  # 103 CSE rounds vs 32 equiv rounds
PROBE_BUDGET_S = 1800.0
RESOURCE_MARKER = "resource/infrastructure limit"

SOURCES = [
    E1 / "equiv_observations.jsonl",
    E1 / "equiv_observations_lane0.jsonl",
    E1 / "equiv_observations_lane1.jsonl",
    E1 / "equiv_observations_lane2.jsonl",
    E1 / "equiv_observations_lane3.jsonl",
    E1 / "equiv_observations_lane4_requeue.jsonl",
]

walls, timeout_hist, resource_hist = {}, set(), set()
likely_by_kernel = {}
seen_probes = set()  # dedupe: post-merge the global file repeats lane rows
for path in SOURCES:
    if not path.exists():
        continue
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        kernel = row["kernel"]
        if row.get("timed_out"):
            timeout_hist.add(kernel)
        if RESOURCE_MARKER in line or row.get("inconclusive_class") == "out_of_memory":
            resource_hist.add(kernel)
        if row["probe_id"] in seen_probes:
            continue
        seen_probes.add(row["probe_id"])
        walls.setdefault(kernel, []).append(row["wall_ms"] / 1000)
        if row.get("evidence_grade") == "LIKELY_EQUIVALENT":
            likely_by_kernel.setdefault(kernel, []).append(row["probe_id"])

# Archived timeout records also count as timeout history.
for archive in ("equiv_observations_timeout_v1.jsonl",
                "equiv_observations_timeout_v2.jsonl"):
    p = E1 / archive
    if p.exists():
        for line in open(p, encoding="utf-8"):
            if line.strip():
                row = json.loads(line)
                timeout_hist.add(row["kernel"])
                if RESOURCE_MARKER in line:
                    resource_hist.add(row["kernel"])

loads, per_kernel, heavy = {}, {}, set()
for kernel, probe_ids in sorted(likely_by_kernel.items()):
    med = statistics.median(walls[kernel])
    is_heavy = (kernel in timeout_hist or kernel in resource_hist
                or med > HEAVY_WALL_S)
    if is_heavy:
        heavy.add(kernel)
    per_probe = min(PROBE_BUDGET_S, med * CSE_ROUNDS_RATIO)
    loads[kernel] = per_probe * len(probe_ids)
    per_kernel[kernel] = {
        "likely_probes": len(probe_ids),
        "equiv_wall_median_s": round(med, 1),
        "cse_per_probe_est_s": round(per_probe, 1),
        "timeout_history": kernel in timeout_hist,
        "resource_history": kernel in resource_hist,
        "heavy": is_heavy,
    }

heavy_sorted = sorted(heavy, key=lambda k: (-loads[k], k))
light_loads = {k: v for k, v in loads.items() if k not in heavy}
light_lanes, light_totals = plan_equiv_lanes(light_loads, [], n_lanes=2)
lanes = [heavy_sorted, light_lanes[0], light_lanes[1]]
totals = [sum(loads[k] for k in heavy_sorted), light_totals[0], light_totals[1]]

flat = [k for lane in lanes for k in lane]
assert len(flat) == len(set(flat)), "CSE lanes overlap"
assert set(flat) == set(likely_by_kernel), "CSE lanes != LIKELY kernel set"

plan = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "criteria": {
        "heavy_wall_s": HEAVY_WALL_S,
        "cse_rounds_ratio": round(CSE_ROUNDS_RATIO, 3),
        "probe_budget_s": PROBE_BUDGET_S,
        "rule": "timeout_history OR resource_history OR wall_median>300s",
    },
    "memory_fractions": {"lane0": 0.92, "lane1": 0.45, "lane2": 0.45},
    "heavy_kernels": sorted(heavy),
    "lanes": [
        {
            "lane": i,
            "role": "heavy-serial" if i == 0 else "light-parallel",
            "kernels": lanes[i],
            "kernel_count": len(lanes[i]),
            "probe_count": sum(per_kernel[k]["likely_probes"] for k in lanes[i]),
            "est_seconds": round(totals[i], 1),
            "est_hours": round(totals[i] / 3600, 2),
        }
        for i in range(3)
    ],
    "per_kernel": per_kernel,
}
(E1 / "cse_lane_plan.json").write_text(json.dumps(plan, indent=1),
                                       encoding="utf-8")
total_likely = sum(len(v) for v in likely_by_kernel.values())
print(f"LIKELY probes: {total_likely} across {len(likely_by_kernel)} kernels")
for entry in plan["lanes"]:
    print(f"lane {entry['lane']} ({entry['role']}): "
          f"kernels={entry['kernel_count']} probes={entry['probe_count']} "
          f"est={entry['est_hours']}h")
print("heavy kernels:", ",".join(sorted(heavy)))
print("CSE_PLAN_OK")
