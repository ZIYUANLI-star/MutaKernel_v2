"""Analyze the B9 task table / unit size table / calibration results so far."""
import io

import _remote

ANALYZE = r'''
import json, collections, statistics
from pathlib import Path

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
tt = json.loads((OUT / "task_table.json").read_text())
print("== task_table type:", type(tt).__name__)
if isinstance(tt, dict):
    print("keys:", list(tt.keys())[:20])
    for k in list(tt.keys())[:3]:
        v = tt[k]
        print("  sample", k, "->", json.dumps(v)[:400] if not isinstance(v, list) else ("list len %d, first=%s" % (len(v), json.dumps(v[0])[:400])))
    rows = tt.get("units") or tt.get("tasks") or tt.get("plan") or []
else:
    rows = tt
print("== rows:", len(rows))
if rows:
    print("first row:", json.dumps(rows[0], indent=2)[:900])

ust = json.loads((OUT / "unit_size_table.json").read_text())
print("\n== unit_size_table type:", type(ust).__name__, "len", len(ust))
if isinstance(ust, dict):
    ks = list(ust.keys())
    print("keys sample:", ks[:5])
    print("first val:", json.dumps(ust[ks[0]], indent=2)[:700])
    items = [(k, v) for k, v in ust.items()]
else:
    items = [(r.get("unit") or r.get("unit_key"), r) for r in ust]

# corpus / level breakdown of units
def corpus_of(key):
    return key.split("_")[0] if key else "?"
lvl = collections.Counter()
for k, v in items:
    lvl[k.split("_")[0]] += 1
print("\n== unit key prefixes:", dict(lvl))

# size distribution
def getnum(v):
    for f in ("total_elements", "numel", "elements", "max_numel", "peak_elements"):
        if isinstance(v, dict) and f in v:
            return v[f]
    return None
nums = [(k, getnum(v)) for k, v in items]
nums = [(k, n) for k, n in nums if isinstance(n, (int, float))]
print("== units with element counts:", len(nums))
if nums:
    nums.sort(key=lambda x: -x[1])
    print("top 12 biggest:")
    for k, n in nums[:12]:
        print("   %-40s %.3e elements  est %.1f GB @34B" % (k, n, n * 34 / 1e9))
    vals = [n for _, n in nums]
    print("median %.3e  mean %.3e  sum %.3e" % (statistics.median(vals), statistics.mean(vals), sum(vals)))
    over = [(k, n) for k, n in nums if n * 34 / 1e9 > 100]
    print("units estimated >100GB:", len(over), [k for k, _ in over])
'''

CALIB = r'''
import json, collections
from pathlib import Path
OUT = Path("/root/mk_v2_runs/e3_b9_calib")
rows = []
for p in sorted(OUT.glob("calibration_*lane*.jsonl")):
    for line in p.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
print("== calibration rows:", len(rows))
if rows:
    print("fields:", sorted(rows[0].keys()))
    for r in rows:
        print(json.dumps(r)[:600])
print("\n== units dir")
for d in sorted((OUT / "units").iterdir()):
    files = sorted(x.name for x in d.iterdir())
    print(" ", d.name, files[:6], "..." if len(files) > 6 else "")
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(ANALYZE.encode()), "/root/_h3_analyze.py")
sftp.putfo(io.BytesIO(CALIB.encode()), "/root/_h3_calib.py")
sftp.close()
for cmd in ["/root/miniconda3/bin/python /root/_h3_analyze.py",
            "/root/miniconda3/bin/python /root/_h3_calib.py",
            "ls /root/mk_v2/_b9_resume_prep.py /root/mk_v2/_b9_calib_driver_v2.py",
            "grep -rn 'oom_kill' /root/mk_v2/_signoff_orch.py | head -20"]:
    print("\n#### " + cmd)
    _remote.run(c, cmd, timeout=240)
c.close()
print("\nH3_DONE")
