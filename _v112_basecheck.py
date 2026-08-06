"""v1.12 survey step 4: recompute Table 10 Killed/stillborn/excluded from baseline ledger (read-only)."""
import _remote

REMOTE_PY = "/root/miniconda3/bin/python"

REMOTE_SCRIPT = r'''
import json, collections
E1 = "/root/mk_v2_runs/e1/"
killed = collections.Counter(); still = collections.Counter()
excl = collections.Counter(); surv = collections.Counter()
outcome_all = collections.Counter()
n = 0
with open(E1 + "baseline_observations.jsonl") as f:
    for line in f:
        r = json.loads(line); n += 1
        c = r.get("operator_category")
        o = r.get("baseline_outcome") or r.get("outcome") or r.get("verdict")
        outcome_all[o] += 1
        if o == "killed": killed[c] += 1
        elif o in ("stillborn", "compile_failed"): still[c] += 1
        elif o == "survived": surv[c] += 1
        else: excl[o] += 0
print("total", n)
print("outcomes:", dict(outcome_all))
print("killed per cat:", dict(killed), "sum", sum(killed.values()))
print("stillborn per cat:", dict(still), "sum", sum(still.values()))
print("survived per cat:", dict(surv), "sum", sum(surv.values()))
print("BASECHECK_DONE")
'''

c = _remote.connect()
_remote.run(c, "cat > /tmp/_v112_base.py << 'PYEOF'\n" + REMOTE_SCRIPT + "\nPYEOF")
_remote.run(c, REMOTE_PY + " /tmp/_v112_base.py", timeout=300)
_remote.run(c, "rm -f /tmp/_v112_base.py")
c.close()
