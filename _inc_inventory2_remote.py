"""Remote READ-ONLY pass 2: guard v9 script + progress lines, the 4 fresh
lane-3/4/5 records, equiv-archive closure, vram classes for risk kernels,
and lane3 queue position of P96.  Writes _inc_inventory2_report.json."""
import json
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
RUNS = Path("/root/mk_v2_runs")
rep = {}

# guard v9 (the running one) + progress-line samples from lane logs
g = RUNS / "e1_guard_cse_split.sh"
rep["guard_v9"] = g.read_text(encoding="utf-8") if g.exists() else None
samples = []
for L in (3, 4, 5):
    log = RUNS / f"e1_cse_lane{L}.log"
    if log.exists():
        lines = log.read_text(encoding="utf-8",
                              errors="replace").splitlines()
        samples.append({
            "lane": L,
            "guard_lines": [l for l in lines if "guard" in l][-4:],
            "tail": lines[-4:],
        })
rep["lane_logs"] = samples

# fresh records in active lanes 3/4/5
fresh = []
for L in (3, 4, 5):
    p = E1 / f"cse_observations_lane{L}.jsonl"
    if not p.exists():
        continue
    for line in open(p, encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        fresh.append({
            "lane": L, "probe_id": row["probe_id"],
            "outcome": row["outcome"],
            "wall_s": round((row.get("wall_ms") or 0) / 1000),
            "timed_out": row.get("timed_out"),
            "evidence": row.get("evidence"),
            "n_trials": len(row.get("trials") or []),
        })
rep["fresh_345"] = fresh

# equiv archive closure: every archived probe must have a final grade in the
# merged file, and it must not be INCONCLUSIVE
final = {}
for line in open(E1 / "equiv_observations.jsonl", encoding="utf-8"):
    row = json.loads(line)
    final[row["probe_id"]] = row.get("evidence_grade")
arch_ids = set()
for name in ("equiv_observations_timeout_v1.jsonl",
             "equiv_observations_timeout_v2.jsonl"):
    p = E1 / name
    if p.exists():
        for line in open(p, encoding="utf-8"):
            if line.strip():
                arch_ids.add(json.loads(line)["probe_id"])
missing = sorted(p for p in arch_ids if p not in final)
still_inc = sorted(p for p in arch_ids if final.get(p) == "INCONCLUSIVE")
from collections import Counter
rep["equiv_closure"] = {
    "archived_unique": len(arch_ids),
    "missing_from_merged": missing,
    "still_inconclusive_in_merged": still_inc,
    "final_grade_dist": dict(Counter(final[p] for p in arch_ids
                                     if p in final)),
    "merged_grade_dist": dict(Counter(final.values())),
}

# the single merged INC record in full (state-sync legitimate refusal)
for line in open(E1 / "equiv_observations.jsonl", encoding="utf-8"):
    row = json.loads(line)
    if row.get("evidence_grade") == "INCONCLUSIVE":
        row.pop("trials", None)
        rep["equiv_merged_inc"] = row
        break

# vram classes + lane assignment for the risk kernels
plan = json.loads((E1 / "cse_lane_plan.json").read_text())
kernels = ["L1_P16", "L1_P19", "L1_P20", "L1_P21", "L1_P22", "L1_P23",
           "L1_P24", "L1_P96"]
rep["vram_classes"] = {
    k: (plan.get("vram_classification", {}).get(k) or {}).get("class")
    for k in kernels}
rep["lane_kernels"] = {i: plan["lanes"][i]["kernels"] for i in (3, 4, 5)}
rep["per_kernel_medians"] = {
    k: plan["per_kernel"][k].get("equiv_wall_median_s")
    for k in kernels if k in plan.get("per_kernel", {})}

out = E1 / "_inc_inventory2_report.json"
out.write_text(json.dumps(rep, indent=1), encoding="utf-8")
print("INVENTORY2_OK")
