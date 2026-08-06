"""v1.12 survey step 3: equiv per-category grades with correct field name (read-only)."""
import _remote

REMOTE_PY = "/root/miniconda3/bin/python"

REMOTE_SCRIPT = r'''
import json, glob, collections

E1 = "/root/mk_v2_runs/e1/"
cat = {}
with open(E1 + "baseline_observations.jsonl") as f:
    for line in f:
        r = json.loads(line)
        cat[r["probe_id"]] = r.get("operator_category")

# exactly the merged_from set of equiv_summary.json (timeout_v1/v2 are superseded archives)
files = [E1 + f for f in (
    "equiv_observations.jsonl",
    "equiv_observations_lane0.jsonl",
    "equiv_observations_lane1.jsonl",
    "equiv_observations_lane2.jsonl",
    "equiv_observations_lane3.jsonl",
    "equiv_observations_lane4_requeue.jsonl",
)]
# show keys of one record
with open(files[0]) as f:
    r0 = json.loads(f.readline())
print("sample keys:", sorted(r0.keys()))

eq = {}
for fn in files:
    with open(fn) as f:
        for line in f:
            r = json.loads(line)
            g = None
            for k in ("evidence_grade", "equivalence_grade", "final_grade", "grade", "verdict", "result", "status"):
                if r.get(k):
                    g = r[k]; break
            if g is None:
                # look one level deep
                for v in r.values():
                    if isinstance(v, dict):
                        for k in ("grade", "equivalence_grade"):
                            if v.get(k):
                                g = v[k]; break
                    if g: break
            eq[r["probe_id"]] = g
print("merged n=", len(eq), "grades:", dict(collections.Counter(eq.values())))
percat = collections.defaultdict(collections.Counter)
for pid, g in eq.items():
    percat[cat.get(pid)][str(g)] += 1
for k in sorted(percat):
    print("cat", k, dict(percat[k]))
# the single INCONCLUSIVE probe
for pid, g in eq.items():
    if g and "INCONC" in str(g).upper():
        print("INC probe:", pid, "cat:", cat.get(pid))
print("EQUIVCAT_DONE")
'''

c = _remote.connect()
_remote.run(c, "cat > /tmp/_v112_eqcat.py << 'PYEOF'\n" + REMOTE_SCRIPT + "\nPYEOF")
_remote.run(c, REMOTE_PY + " /tmp/_v112_eqcat.py", timeout=300)
_remote.run(c, "rm -f /tmp/_v112_eqcat.py")
c.close()
