"""Read-only: inspect equiv record schema, then witnessed-by-category."""
import _remote

AGG = r"""
import json
from collections import Counter

E1 = "/root/mk_v2_runs/e1/"

cat = {}
for l in open(E1 + "baseline_observations.jsonl"):
    if l.strip():
        r = json.loads(l)
        cat[r["probe_id"]] = r.get("operator_category")

recs = [json.loads(l) for l in open(E1 + "equiv_observations.jsonl") if l.strip()]
print("keys sample:", sorted(recs[0].keys()))
# find the grade-ish field
for k in recs[0].keys():
    vals = Counter(str(r.get(k)) for r in recs)
    if any("EQUIV" in v or "WITNESS" in v for v in vals):
        print("grade field:", k, dict(vals))

# use detected field
gf = None
for k in recs[0].keys():
    if any("WITNESS" in str(r.get(k)) for r in recs[:50]) or any("WITNESS" in str(r.get(k)) for r in recs):
        gf = k
        break
print("using field:", gf)
wit = [r["probe_id"] for r in recs if "WITNESS" in str(r.get(gf))]
print("witnessed n =", len(wit))
print("witnessed by cat:", dict(Counter(cat.get(p, "?") for p in wit)))
likely = [r["probe_id"] for r in recs if "LIKELY" in str(r.get(gf))]
print("likely n =", len(likely), "by cat:", dict(Counter(cat.get(p, "?") for p in likely)))
print("summary json:", open(E1 + "equiv_summary.json").read()[:400])
print("AGG2_DONE")
"""

c = _remote.connect()
s = c.open_sftp()
with s.open("/root/mk_v2/_fillable_agg2.py", "w") as f:
    f.write(AGG)
s.close()
_, o, _ = _remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_fillable_agg2.py 2>&1",
                      timeout=300, echo=False)
c.close()
print(o)
print("FILLABLE2_DONE")
