#!/usr/bin/env python3
"""Count remaining P53 (and per-kernel) CSE probes per lane, using the driver's
own target/skip logic. Read-only; does not touch running drivers."""
import json
import sys
from pathlib import Path

ROOT = Path("/root/mk_v2")
sys.path.insert(0, str(ROOT))
OUT = Path("/root/mk_v2_runs/e1")

from scripts.run_e1_cse_falsify import (
    order_kernel_files, load_cse_skip_set, cse_lane_paths,
)
from scripts.run_e1_probe_study import _load_probe_files

plan = json.loads((OUT / "cse_lane_plan.json").read_text())

# LIKELY_EQUIVALENT set
likely = set()
with open(OUT / "equiv_observations.jsonl", encoding="utf-8") as fh:
    for line in fh:
        row = json.loads(line)
        if row.get("evidence_grade") == "LIKELY_EQUIVALENT":
            likely.add(row["probe_id"])

kernel_files_all = _load_probe_files(OUT)

for lane in (3, 4, 5):
    lane_kernels = set(plan["lanes"][lane]["kernels"])
    kf_ordered = order_kernel_files(list(kernel_files_all), plan["lanes"][lane]["kernels"])
    targets = [
        (kf["kernel"]["problem_name"], probe["probe_id"], probe["operator_name"])
        for kf in kf_ordered
        if kf["kernel"]["problem_name"] in lane_kernels
        for probe in kf["probes"]
        if probe["probe_id"] in likely
    ]
    own, skip = load_cse_skip_set(OUT, lane, None)
    total = len(targets)
    done = [t for t in targets if t[1] in skip]
    remaining = [t for t in targets if t[1] not in skip]
    p53_total = [t for t in targets if t[0] == "L1_P53"]
    p53_done = [t for t in p53_total if t[1] in skip]
    p53_remaining = [t for t in p53_total if t[1] not in skip]
    print(f"=== LANE {lane} (kernels={plan['lanes'][lane]['kernels']}) ===")
    print(f"  targets total={total} done={len(done)} remaining={len(remaining)}")
    print(f"  P53 in this lane: total={len(p53_total)} done={len(p53_done)} remaining={len(p53_remaining)}")
    if p53_remaining:
        print("  P53 REMAINING probes (in queue order):")
        for _, pid, op in p53_remaining:
            print("    ", pid)
    # position of first remaining P53 in the remaining queue
    rem_ids = [t[1] for t in remaining]
    first_p53_pos = next((i for i, t in enumerate(remaining) if t[0] == "L1_P53"), None)
    if first_p53_pos is not None:
        print(f"  next-up remaining queue head: {rem_ids[:5]}")
        print(f"  first remaining P53 is at remaining-queue index {first_p53_pos}")
