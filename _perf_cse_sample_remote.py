#!/usr/bin/env python3
"""READ-ONLY sampling of CSE observation files for the slowness analysis.

Runs ON THE REMOTE HOST. Prints a JSON report to stdout. Touches nothing.
"""
import json
import sys
from collections import defaultdict

BASE = "/root/mk_v2_runs/e1"
SEGS = ["state_snapshot_ms", "state_sync_ms", "rng_capture_ms",
        "input_isolation_ms", "reference_ms", "candidate_ms",
        "oracle_ms", "cleanup_ms", "total_ms"]


def analyse_probe(row):
    trials = row.get("trials") or []
    seg_sum = defaultdict(float)
    n_timed = 0
    per_round_totals = []
    extra_keys = set()
    for t in trials:
        tm = t.get("timings_ms")
        if not tm:
            continue
        n_timed += 1
        for k, v in tm.items():
            extra_keys.add(k)
            if isinstance(v, (int, float)):
                seg_sum[k] += v
        if isinstance(tm.get("total_ms"), (int, float)):
            per_round_totals.append(tm["total_ms"])
    wall = row.get("wall_ms") or 0.0
    tot = seg_sum.get("total_ms", 0.0)
    return {
        "probe_id": row.get("probe_id"),
        "kernel": row.get("kernel"),
        "operator": row.get("operator_name"),
        "outcome": row.get("outcome"),
        "wall_ms": wall,
        "n_trials": len(trials),
        "n_timed": n_timed,
        "sum_total_ms": round(tot, 1),
        "out_of_round_ms": round(wall - tot, 1),
        "seg_sums_ms": {k: round(v, 1) for k, v in seg_sum.items()},
        "per_round_total_ms_mean": round(
            sum(per_round_totals) / len(per_round_totals), 2)
        if per_round_totals else None,
        "timing_keys": sorted(extra_keys),
        "n_round_timeouts": sum(1 for t in trials if t.get("round_timeout")),
        "skipped_policies": row.get("skipped_policies"),
    }


def sample_lane(lane, n_max):
    path = f"{BASE}/cse_observations_lane{lane}.jsonl"
    rows = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    except FileNotFoundError:
        return {"lane": lane, "error": "missing"}
    # spread across kernels: keep newest per kernel, then fill.
    by_kernel = defaultdict(list)
    for r in rows:
        by_kernel[r.get("kernel")].append(r)
    picked = []
    for kern in sorted(by_kernel):
        picked.append(by_kernel[kern][-1])
    # fill remaining slots with the longest-wall probes (the pain points)
    rest = sorted((r for r in rows if r not in picked),
                  key=lambda r: -(r.get("wall_ms") or 0))
    picked = picked[:n_max]
    for r in rest:
        if len(picked) >= n_max:
            break
        picked.append(r)
    walls = sorted((r.get("wall_ms") or 0) / 1000.0 for r in rows)
    med = walls[len(walls) // 2] if walls else None
    return {
        "lane": lane,
        "n_rows": len(rows),
        "kernels": sorted(by_kernel),
        "wall_s_median": round(med, 1) if med else None,
        "wall_s_min": round(walls[0], 1) if walls else None,
        "wall_s_max": round(walls[-1], 1) if walls else None,
        "samples": [analyse_probe(r) for r in picked],
    }


def main():
    report = {}
    for lane, n in [(3, 8), (4, 8), (1, 4), (2, 4)]:
        report[f"lane{lane}"] = sample_lane(lane, n)
    # one full trial record (keys only + one timings dict) for schema check
    try:
        with open(f"{BASE}/cse_observations_lane3.jsonl", encoding="utf-8") as fh:
            row = json.loads(fh.readline())
        tr = (row.get("trials") or [{}])[0]
        report["schema"] = {
            "record_keys": sorted(row.keys()),
            "trial_keys": sorted(tr.keys()),
            "trial_example_timings": tr.get("timings_ms"),
        }
    except Exception as exc:
        report["schema"] = {"error": str(exc)}
    json.dump(report, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
