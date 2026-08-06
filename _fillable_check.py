"""Read-only aggregation: which blueprint cells are now backed by closed data.

Computes (1) CSE final tally, (2) witnessed non-eq by operator category
(equiv 74 + CSE 9), (3) per-category survivor bookkeeping for Table 10,
(4) witness-confirmation run progress.
"""
import _remote

AGG = r"""
import json, glob
from collections import Counter, defaultdict

E1 = "/root/mk_v2_runs/e1/"

# probe_id -> operator_category from baseline ledger
cat = {}
surv = set()
for l in open(E1 + "baseline_observations.jsonl"):
    if not l.strip():
        continue
    r = json.loads(l)
    cat[r["probe_id"]] = r.get("operator_category")
    if r.get("outcome") == "survived" or r.get("validation_status") == "pass":
        pass
print("baseline probes:", len(cat))

# equiv ledger (post signoff amendment)
eq = {}
for l in open(E1 + "equiv_observations.jsonl"):
    if not l.strip():
        continue
    r = json.loads(l)
    eq[r["probe_id"]] = r.get("grade") or r.get("outcome") or r.get("equiv_grade")
c = Counter(eq.values())
print("equiv ledger:", len(eq), dict(c))

# CSE final ledger
cse = {}
for path in sorted(glob.glob(E1 + "cse_observations_lane*.jsonl")):
    if ".bak" in path:
        continue
    for l in open(path):
        if not l.strip():
            continue
        r = json.loads(l)
        o = r.get("outcome")
        if o == "INCONCLUSIVE" and "archive" not in path and "timeout_v1" not in path:
            cse[r["probe_id"]] = o
        elif o != "INCONCLUSIVE":
            cse[r["probe_id"]] = o
print("cse unique probes:", len(cse), dict(Counter(cse.values())))

# witnessed by category
wit_eq = [p for p, g in eq.items() if "WITNESSED" in (g or "")]
wit_cse = [p for p, g in cse.items() if g == "FALSIFIED"]
print("witness counts: equiv", len(wit_eq), "cse", len(wit_cse),
      "overlap", len(set(wit_eq) & set(wit_cse)))
bycat_eq = Counter(cat.get(p, "?") for p in wit_eq)
bycat_cse = Counter(cat.get(p, "?") for p in wit_cse)
bycat_all = Counter(cat.get(p, "?") for p in set(wit_eq) | set(wit_cse))
print("witnessed by cat (equiv):", dict(bycat_eq))
print("witnessed by cat (cse):", dict(bycat_cse))
print("witnessed by cat (total):", dict(bycat_all))

# still-likely by cat
sle = [p for p, g in cse.items() if g == "STILL_LIKELY_EQUIVALENT"]
print("still_likely by cat:", dict(Counter(cat.get(p, "?") for p in sle)), "n=", len(sle))

# cse falsified probe list with witnesses
print("\nFALSIFIED detail:")
for path in sorted(glob.glob(E1 + "cse_observations_lane*.jsonl")):
    if ".bak" in path:
        continue
    for l in open(path):
        if not l.strip():
            continue
        r = json.loads(l)
        if r.get("outcome") == "FALSIFIED":
            print(" ", r["probe_id"], "| cat", cat.get(r["probe_id"]),
                  "| witness", r.get("witness_policy"), r.get("witness_substream"),
                  r.get("witness_seed"))

# witness confirmation progress
import os
wc = "/root/mk_v2_runs/e1/witness_confirmation/"
for f in sorted(glob.glob(wc + "*.jsonl")):
    n = sum(1 for x in open(f) if x.strip())
    print("WC", os.path.basename(f), n)
for f in ("STAGE_DONE_LANE0", "STAGE_DONE_LANE1", "plan.json"):
    print("WC exists", f, os.path.exists(wc + f))
print("AGG_DONE")
"""

c = _remote.connect()
s = c.open_sftp()
with s.open("/root/mk_v2/_fillable_agg.py", "w") as f:
    f.write(AGG)
s.close()
_, o, _ = _remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_fillable_agg.py 2>&1",
                      timeout=300, echo=False)
c.close()
print(o)
print("FILLABLE_DONE")
