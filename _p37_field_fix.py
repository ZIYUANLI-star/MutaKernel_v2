"""7.4-1: fix P37 policy_skip_reason field in ledgers; verify P95 category.

Scans all live E1 ledgers for rows carrying policy_skip_reason ==
'resource_domain_violation' on P37 probes and rewrites the reason to
'oracle_indiscriminative_for_kernel' with a 'reclassified' provenance tag.
Also reports P95 witnessed rows and their operator_category.
"""
import glob
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
TS = datetime.now().strftime("%Y%m%dT%H%M%S")
now = datetime.now(timezone.utc).isoformat()

def fix_obj(o, hits):
    """Recursively fix policy_skip_reason in nested dicts/lists."""
    if isinstance(o, dict):
        if o.get("policy_skip_reason") == "resource_domain_violation":
            o["policy_skip_reason"] = "oracle_indiscriminative_for_kernel"
            o["reclassified"] = "kernel_numeric_sensitivity"
            o["reclassified_at"] = now
            o["reclassified_basis"] = "清算表 7.4-1"
            hits.append(True)
        for v in o.values():
            fix_obj(v, hits)
    elif isinstance(o, list):
        for v in o:
            fix_obj(v, hits)

total = 0
for f in sorted(glob.glob(str(E1 / "*.jsonl"))):
    rows = []
    file_hits = 0
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            hits = []
            if "P37" in str(r.get("probe_id", "")):
                fix_obj(r, hits)
            if hits:
                file_hits += len(hits)
            rows.append(r)
    if file_hits:
        shutil.copy2(f, f + ".bak_p37fix_" + TS)
        tmp = f + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")
        Path(tmp).replace(f)
        print("FIXED %s: %d occurrences" % (f, file_hits))
        total += file_hits

# also scan requeue_final dir
for f in sorted(glob.glob(str(E1 / "requeue_final" / "*.jsonl"))):
    rows = []
    file_hits = 0
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            hits = []
            if "P37" in str(r.get("probe_id", "")):
                fix_obj(r, hits)
            if hits:
                file_hits += len(hits)
            rows.append(r)
    if file_hits:
        shutil.copy2(f, f + ".bak_p37fix_" + TS)
        tmp = f + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")
        Path(tmp).replace(f)
        print("FIXED %s: %d occurrences" % (f, file_hits))
        total += file_hits

print("P37_FIELD_FIX total occurrences:", total)

# P95 verification
cat = {}
for line in open(E1 / "baseline_observations.jsonl", encoding="utf-8"):
    r = json.loads(line)
    cat[r["probe_id"]] = r.get("operator_category")
for line in open(E1 / "equiv_observations.jsonl", encoding="utf-8"):
    r = json.loads(line)
    pid = r.get("probe_id", "")
    if "P95" in pid and r.get("evidence_grade") == "WITNESSED_NON_EQUIVALENT":
        ev = json.dumps(r.get("evidence"))[:200]
        print("P95 witnessed:", pid, "category=", cat.get(pid),
              "divergence=", r.get("divergence"), "evidence~", ev)
print("DONE")
