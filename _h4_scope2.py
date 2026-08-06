"""Precise B9 scope: task table stats, unit sizes, corpus->task mapping."""
import io

import _remote

SCRIPT = r'''
import json, collections, statistics
from pathlib import Path

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
tt = json.loads((OUT / "task_table.json").read_text())
print("== task_table meta")
for k in ("created_at", "source_contract_draft", "source_sha256", "n_tasks",
          "n_units", "n_reduction_heavy"):
    print("  ", k, "=", tt.get(k))
print("   gaps =", json.dumps(tt.get("gaps"))[:1500])
tasks = tt["tasks"]
print("== tasks:", len(tasks))
lv = collections.Counter(t.get("level") for t in tasks)
print("   level dist:", dict(lv))
dt = collections.Counter(tuple(t.get("dtypes", [])) for t in tasks)
print("   dtype combos:", {str(k): v for k, v in dt.items()})
rh = collections.Counter(bool(t.get("reduction_heavy")) for t in tasks)
print("   reduction_heavy:", dict(rh))
n_units = sum(len(t.get("dtypes", [])) for t in tasks)
n_units_rh = sum(len(t.get("dtypes", [])) for t in tasks if t.get("reduction_heavy"))
print("   units total = %d ; reduction_heavy units = %d ; non-rh units = %d"
      % (n_units, n_units_rh, n_units - n_units_rh))
prefix = collections.Counter(t["task_key"].split("_")[0] for t in tasks)
print("   task_key prefixes:", dict(prefix))
# any non-KernelBench file paths (e.g. TritonBench)?
srcs = collections.Counter(t["file"].split("/")[0] for t in tasks)
print("   file roots:", dict(srcs))

ust = json.loads((OUT / "unit_size_table.json").read_text())
print("\n== unit_size_table meta")
for k in ("created_at", "cmp_bytes_per_elem_measured", "note"):
    print("  ", k, "=", json.dumps(ust.get(k))[:600])
subs = ust["subjects"]
print("   subjects entries:", len(subs), type(subs).__name__)
if isinstance(subs, dict):
    ks = list(subs.keys())
    print("   sample key:", ks[0], "->", json.dumps(subs[ks[0]], indent=2)[:800])
    items = list(subs.items())
else:
    print("   sample:", json.dumps(subs[0], indent=2)[:800])
    items = [(s.get("task_key") or s.get("unit"), s) for s in subs]

def elems(v):
    if not isinstance(v, dict):
        return None
    for f in ("total_elements", "cmp_elements", "elements", "numel",
              "max_elements", "peak_elements", "n_elements"):
        if f in v and isinstance(v[f], (int, float)):
            return v[f]
    return None

rows = [(k, elems(v), v) for k, v in items]
have = [(k, n, v) for k, n, v in rows if n]
print("   with element counts:", len(have), "of", len(rows))
if have:
    have.sort(key=lambda x: -x[1])
    print("   --- top 15 by elements ---")
    for k, n, v in have[:15]:
        print("     %-26s %.4e elem  est_peak=%.1f GB  %s"
              % (k, n, n * 34 / 1e9,
                 {kk: v[kk] for kk in list(v)[:6] if kk != "shapes"}))
    vals = [n for _, n, _ in have]
    print("   median=%.3e mean=%.3e sum=%.4e" % (statistics.median(vals),
                                                 statistics.mean(vals), sum(vals)))
    for thr in (30, 50, 84, 100, 120):
        big = [k for k, n, _ in have if n * 34 / 1e9 > thr]
        print("   est_peak > %3d GB : %3d units  %s" % (thr, len(big), big[:8]))
'''

MAP = r'''
import json, collections
from pathlib import Path
p = Path("/root/mk_v2_runs/e2_reconcile")
print("== e2_reconcile dir")
for f in sorted(p.iterdir()):
    print("  ", f.name, f.stat().st_size)
d = p / "contracts_c2c3c5_draft.jsonl"
if d.is_file():
    rows = [json.loads(l) for l in d.read_text().splitlines() if l.strip()]
    print("== contract draft rows:", len(rows))
    print("   fields:", sorted(rows[0].keys()))
    print("   sample:", json.dumps(rows[0])[:800])
    c = collections.Counter(r.get("corpus") or r.get("corpus_id") for r in rows)
    print("   corpus dist:", dict(c))
    tk = collections.Counter(r.get("task_key") for r in rows)
    print("   distinct task_key:", len(tk))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_h4a.py")
sftp.putfo(io.BytesIO(MAP.encode()), "/root/_h4b.py")
sftp.close()
for cmd in ["/root/miniconda3/bin/python /root/_h4a.py",
            "/root/miniconda3/bin/python /root/_h4b.py",
            "ls /root/mk_v2_runs/ ",
            "sed -n '1,80p' /root/mk_v2/_b9_resume_prep.py"]:
    print("\n#### " + cmd)
    _remote.run(c, cmd, timeout=240)
c.close()
print("\nH4_DONE")
