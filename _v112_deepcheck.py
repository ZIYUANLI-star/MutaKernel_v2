"""v1.12 survey step 2: recompute CSE final distribution + per-category breakdowns (read-only)."""
import _remote

REMOTE_PY = "/root/miniconda3/bin/python"

REMOTE_SCRIPT = r'''
import json, collections

E1 = "/root/mk_v2_runs/e1/"

# operator_category per probe_id from baseline ledger
cat = {}
base = collections.Counter()
with open(E1 + "baseline_observations.jsonl") as f:
    for line in f:
        r = json.loads(line)
        cat[r["probe_id"]] = r.get("operator_category")
        base[r.get("operator_category")] += 1
print("baseline probes per cat:", dict(base), "total", sum(base.values()))

# equiv merged grades per probe (from lane files? use equiv observations)
import glob
equiv_files = sorted(glob.glob(E1 + "equiv_observations*.jsonl"))
print("equiv files:", [f.split("/")[-1] for f in equiv_files])
eq = {}
for fn in equiv_files:
    with open(fn) as f:
        for line in f:
            r = json.loads(line)
            eq[r["probe_id"]] = r.get("grade") or r.get("equiv_grade")
eqc = collections.Counter(eq.values())
print("equiv merged grades:", dict(eqc), "n=", len(eq))
# per-category equiv breakdown
percat = collections.defaultdict(collections.Counter)
for pid, g in eq.items():
    percat[cat.get(pid)][g] += 1
for k in sorted(percat, key=lambda x: str(x)):
    print("equiv cat", k, dict(percat[k]))

# CSE main ledger (6 lanes) + tagged reruns
main_files = ["cse_observations_lane%d.jsonl" % i for i in range(6)]
tag_files = ["cse_observations_lane3_final_requeue.jsonl",
             "cse_observations_lane3_p96_5400.jsonl",
             "cse_observations_lane5_final_requeue.jsonl"]
cse = {}
dup = []
for fn in main_files + tag_files:
    with open(E1 + fn) as f:
        for line in f:
            r = json.loads(line)
            pid = r["probe_id"]
            if pid in cse:
                dup.append(pid)
            cse[pid] = r  # tagged rerun (later file) overrides
print("cse unique probes:", len(cse), "overridden(dups from rerun):", len(dup), dup)

def verdict(r):
    for k in ("final_verdict", "verdict", "grade", "cse_verdict", "outcome"):
        if k in r:
            return r[k]
    return None

vc = collections.Counter(verdict(r) for r in cse.values())
print("cse verdicts:", dict(vc))
fals = sorted(pid for pid, r in cse.items() if "FALSIF" in str(verdict(r)).upper())
print("FALSIFIED list (%d):" % len(fals))
for pid in fals:
    print("   ", pid, "| cat:", cat.get(pid))
# per-cat cse verdicts
percat2 = collections.defaultdict(collections.Counter)
for pid, r in cse.items():
    percat2[cat.get(pid)][str(verdict(r))] += 1
for k in sorted(percat2, key=lambda x: str(x)):
    print("cse cat", k, dict(percat2[k]))

# sanity: cse pool == equiv LIKELY_EQUIVALENT pool?
likely = {p for p, g in eq.items() if g == "LIKELY_EQUIVALENT"}
print("cse pool == equiv LIKELY pool:", set(cse) == likely,
      "| only-in-cse:", len(set(cse) - likely), "| only-in-likely:", len(likely - set(cse)))

# archive check
with open(E1 + "cse_observations_inc_archive_v2.jsonl") as f:
    arc = [json.loads(l)["probe_id"] for l in f]
print("archive n=%d:" % len(arc), arc)
print("DEEPCHECK_DONE")
'''

c = _remote.connect()
_remote.run(c, "cat > /tmp/_v112_deep.py << 'PYEOF'\n" + REMOTE_SCRIPT + "\nPYEOF")
_remote.run(c, REMOTE_PY + " /tmp/_v112_deep.py", timeout=300)
_remote.run(c, "rm -f /tmp/_v112_deep.py")
c.close()
