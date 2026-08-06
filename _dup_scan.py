"""Scan every major ledger on the A800 for duplicated experiment work."""
import _remote

SCRIPT = r'''
import json, glob, os
from collections import Counter

E1 = "/root/mk_v2_runs/e1/"
B9 = "/root/mk_v2_runs/e3_b9_calib/"

def load_jsonl(path):
    recs = []
    try:
        for line in open(path, encoding="utf-8"):
            if line.strip():
                recs.append(json.loads(line))
    except FileNotFoundError:
        pass
    return recs

def dupes(ids):
    c = Counter(ids)
    return {k: v for k, v in c.items() if v > 1}

print("== 1. E1 baseline ==")
recs = load_jsonl(E1 + "baseline_observations.jsonl")
ids = [r.get("probe_id") for r in recs]
print("rows", len(recs), "unique", len(set(ids)), "dupes", dupes(ids))

print()
print("== 2. E1 equiv: global + lanes ==")
files = sorted(glob.glob(E1 + "equiv_observations*.jsonl"))
allids = {}
for f in files:
    recs = load_jsonl(f)
    ids = [r.get("probe_id") for r in recs]
    d = dupes(ids)
    print(os.path.basename(f), "rows", len(recs), "unique", len(set(ids)),
          "dupes_in_file", len(d), (list(d.items())[:5] if d else ""))
    allids[os.path.basename(f)] = set(ids)
names = list(allids)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        inter = allids[names[i]] & allids[names[j]]
        if inter:
            print("OVERLAP", names[i], "&", names[j], len(inter),
                  sorted(inter)[:6])

print()
print("== 3. E1 equiv summary vs completed ==")
try:
    summ = json.load(open(E1 + "equiv_summary.json"))
    print("summary keys:", list(summ.keys())[:8])
except Exception as e:
    print("no summary:", e)
comp_files = sorted(glob.glob(E1 + "equiv_completed*.json"))
seen = {}
for f in comp_files:
    try:
        lst = json.load(open(f))
        if isinstance(lst, list):
            print(os.path.basename(f), len(lst), "unique", len(set(lst)))
            for pid in lst:
                seen.setdefault(pid, []).append(os.path.basename(f))
    except Exception as e:
        print(os.path.basename(f), "ERR", e)
multi = {k: v for k, v in seen.items() if len(v) > 1}
print("probes in >1 completed file:", len(multi), list(multi.items())[:5])

print()
print("== 4. CSE lanes ==")
files = sorted(glob.glob(E1 + "cse_observations*.jsonl"))
allids = {}
tot = 0
for f in files:
    recs = load_jsonl(f)
    ids = [r.get("probe_id") for r in recs]
    tot += len(recs)
    d = dupes(ids)
    print(os.path.basename(f), "rows", len(recs), "unique", len(set(ids)),
          "dupes_in_file", len(d), (list(d.items())[:5] if d else ""))
    allids[os.path.basename(f)] = set(ids)
names = list(allids)
inter_tot = set()
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        inter = allids[names[i]] & allids[names[j]]
        if inter:
            inter_tot |= inter
            print("OVERLAP", names[i], "&", names[j], len(inter),
                  sorted(inter)[:6])
print("total rows", tot, "cross-lane duplicated probe_ids:", len(inter_tot))

print()
print("== 5. B9 v2 rows ==")
rows = []
for f in sorted(glob.glob(B9 + "calibration_v2_lane*.jsonl")):
    rows += [(os.path.basename(f), r) for r in load_jsonl(f)]
units = [r.get("unit") for _, r in rows]
d = dupes(units)
print("v2 rows", len(rows), "unique units", len(set(units)),
      "duplicated units", len(d))
for u, n in sorted(d.items()):
    srcs = [(f, r.get("started_at"), r.get("control_status")) for f, r in rows
            if r.get("unit") == u]
    print("  ", u, "x%d" % n, srcs)

print()
print("== 6. B9 v1 vs v2 unit overlap ==")
v1units = []
for f in sorted(glob.glob(B9 + "calibration_lane*.jsonl")):
    v1units += [r.get("unit") or r.get("task_key") for r in load_jsonl(f)]
print("v1 rows", len(v1units), "unique", len(set(v1units)))
ov = set(v1units) & set(units)
print("units in BOTH v1 and v2:", len(ov), sorted(ov)[:10])

print()
print("== 7. B9 queue done vs rows ==")
qs = json.load(open(B9 + "queue_state.json"))
qdone = set(qs["done"])
rowset = set(units)
print("queue done", len(qdone), "| rows for done units missing:",
      len(qdone - rowset), sorted(qdone - rowset)[:6])
print("rows without queue done entry:", len(rowset - qdone),
      sorted(rowset - qdone)[:10])

print()
print("== 8. E0 runs overlap ==")
import re
e0 = "/root/mk_v2_runs/"
for d in sorted(glob.glob(e0 + "e0_*")):
    obs = os.path.join(d, "observations.jsonl")
    if os.path.exists(obs):
        recs = load_jsonl(obs)
        key = [r.get("probe_id") or r.get("config_id") for r in recs]
        dd = dupes(key)
        print(os.path.basename(d), "rows", len(recs),
              "unique", len(set(key)), "dupes", len(dd))

print()
print("== 9. WC cells ==")
cells = glob.glob("/root/mk_v2_runs/e1/witness_confirmation/cells/*.json")
names = [os.path.basename(c) for c in cells]
print("cells", len(cells), "unique names", len(set(names)))
'''

c = _remote.connect()
_, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF\n",
                      timeout=600, echo=False)
c.close()
print(o)
if e.strip():
    print("STDERR:", e[-1500:])
print("DUP_SCAN_DONE")
