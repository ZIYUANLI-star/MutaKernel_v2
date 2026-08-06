#!/usr/bin/env python3
"""Compute blueprint batch-1 numbers from the amended E1 ledgers.

Produces /root/mk_v2_runs/e1/amendment_v1/blueprint_batch1.json with:
  * Table 10 per-operator-category: probes, killed, machine_proven,
    witnessed_survived, detection_rate = killed / (killed + witnessed)
    (INCONCLUSIVE column stays open pending the blinded human audit,
    per 清算表 §7.4-3)
  * §5.5 CSE falsification sentence: falsified count / 453 (%)
  * final ledger counts (equiv + cse) with dedup by latest finished_at
"""
import glob
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
OUT = E1 / "amendment_v1" / "blueprint_batch1.json"

# probe_id -> operator_category from baseline observations
cat = {}
base_status = Counter()
cat_counts = Counter()
killed = Counter()
machine = Counter()
for line in open(E1 / "baseline_observations.jsonl", encoding="utf-8"):
    r = json.loads(line)
    pid = r["probe_id"]
    c = r.get("operator_category")
    cat[pid] = c
    cat_counts[c] += 1
    base_status[r.get("status")] += 1
    if r.get("status") == "killed":
        killed[c] += 1
    if r.get("status") == "machine_proven_equivalent":
        machine[c] += 1

# amended equiv ledger
eq = {}
for line in open(E1 / "equiv_observations.jsonl", encoding="utf-8"):
    r = json.loads(line)
    eq[r["probe_id"]] = r
eq_grades = Counter(r.get("evidence_grade") for r in eq.values())
witnessed = Counter()
witnessed_probes = []
for pid, r in eq.items():
    if r.get("evidence_grade") == "WITNESSED_NON_EQUIVALENT":
        witnessed[cat.get(pid)] += 1
        witnessed_probes.append(pid)

# amended cse ledgers (dedup latest)
cse = {}
for f in sorted(glob.glob(str(E1 / "cse_observations_lane*.jsonl"))):
    for line in open(f, encoding="utf-8"):
        r = json.loads(line)
        pid = r["probe_id"]
        prev = cse.get(pid)
        if prev is None or str(r.get("finished_at", "")) >= \
                str(prev.get("finished_at", "")):
            cse[pid] = r
cse_outcomes = Counter(r.get("outcome") for r in cse.values())
falsified = sorted(pid for pid, r in cse.items()
                   if r.get("outcome") == "FALSIFIED")
fals_classes = Counter(cse[pid].get("fault_class") for pid in falsified)

# fault-class distribution of witnessed (equiv)
wit_classes = Counter(eq[pid].get("fault_class") for pid in witnessed_probes)

table10 = {}
order = ["A", "B", "C", "D"]
tot = {"probes": 0, "killed": 0, "machine": 0, "witnessed": 0}
for c in order:
    k, m, w = killed[c], machine[c], witnessed[c]
    det = k / (k + w) if (k + w) else None
    table10[c] = {"probes": cat_counts[c], "killed": k,
                  "machine_proven_eq": m, "witnessed_surv": w,
                  "detection_rate_witnessed": round(100 * det, 1)
                  if det is not None else None}
    tot["probes"] += cat_counts[c]
    tot["killed"] += k
    tot["machine"] += m
    tot["witnessed"] += w
det = tot["killed"] / (tot["killed"] + tot["witnessed"])
table10["Overall"] = {"probes": tot["probes"], "killed": tot["killed"],
                      "machine_proven_eq": tot["machine"],
                      "witnessed_surv": tot["witnessed"],
                      "detection_rate_witnessed": round(100 * det, 1)}
miss_rate = 100 * tot["witnessed"] / (tot["killed"] + tot["witnessed"])

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "source": "amended ledgers (wc1_closure_v1)",
    "baseline_status_counts": dict(base_status),
    "equiv_final_grades": dict(eq_grades),
    "cse_unique_probes": len(cse),
    "cse_final_outcomes": dict(cse_outcomes),
    "cse_falsified_probes": falsified,
    "cse_falsified_fault_classes": dict(fals_classes),
    "cse_sentence": {
        "falsified": len(falsified), "of": 453,
        "pct": round(100 * len(falsified) / 453, 1),
    },
    "equiv_witnessed_fault_classes": dict(wit_classes),
    "table10": table10,
    "rq4_miss_rate_pct": round(miss_rate, 1),
    "notes": [
        "detection_rate_witnessed = killed / (killed + witnessed_survived)",
        "INCONCLUSIVE column deliberately left open (blinded audit pending)",
        "witnessed includes P95 crash-type SPEC_VIOLATION (footnote per "
        "清算表 7.4-2) and P68/P98 intermittent (annotated)",
    ],
}
OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
               encoding="utf-8")
print(json.dumps(payload, indent=1, ensure_ascii=False))
