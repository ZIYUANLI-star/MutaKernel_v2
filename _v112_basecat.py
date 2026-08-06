"""Recompute Table 10 Killed / stillborn per operator_category (read-only)."""
import _remote

REMOTE_PY = "/root/miniconda3/bin/python"

REMOTE_SCRIPT = r'''
import json, collections
E1 = "/root/mk_v2_runs/e1/"
tab = collections.defaultdict(collections.Counter)
with open(E1 + "baseline_observations.jsonl") as f:
    for line in f:
        r = json.loads(line)
        tab[r["status"]][r["operator_category"]] += 1
for s in ("killed", "stillborn", "survived", "machine_proven_equivalent"):
    print(s, dict(sorted(tab[s].items())), "sum", sum(tab[s].values()))
print("BASECAT_DONE")
'''

c = _remote.connect()
_remote.run(c, "cat > /tmp/_v112_bc.py << 'PYEOF'\n" + REMOTE_SCRIPT + "\nPYEOF")
_remote.run(c, REMOTE_PY + " /tmp/_v112_bc.py", timeout=300)
_remote.run(c, "rm -f /tmp/_v112_bc.py")
c.close()
