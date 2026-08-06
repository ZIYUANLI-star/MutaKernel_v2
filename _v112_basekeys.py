"""Inspect baseline record keys then recompute killed/stillborn per category."""
import _remote

REMOTE_PY = "/root/miniconda3/bin/python"

REMOTE_SCRIPT = r'''
import json, collections
E1 = "/root/mk_v2_runs/e1/"
with open(E1 + "baseline_observations.jsonl") as f:
    r0 = json.loads(f.readline())
print("keys:", sorted(r0.keys()))
print("sample:", {k: r0[k] for k in sorted(r0.keys()) if not isinstance(r0[k], (dict, list))})

# guess verdict-like fields from value inspection
cnt = collections.defaultdict(collections.Counter)
with open(E1 + "baseline_observations.jsonl") as f:
    for line in f:
        r = json.loads(line)
        for k, v in r.items():
            if isinstance(v, str) and len(v) < 40:
                cnt[k][v] += 1
for k in cnt:
    if len(cnt[k]) <= 15:
        print(k, "=>", dict(cnt[k]))
print("BASEKEYS_DONE")
'''

c = _remote.connect()
_remote.run(c, "cat > /tmp/_v112_bk.py << 'PYEOF'\n" + REMOTE_SCRIPT + "\nPYEOF")
_remote.run(c, REMOTE_PY + " /tmp/_v112_bk.py", timeout=300)
_remote.run(c, "rm -f /tmp/_v112_bk.py")
c.close()
