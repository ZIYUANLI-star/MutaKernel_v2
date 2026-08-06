# -*- coding: utf-8 -*-
"""Survey remote state for the B9 quantile fix: deployed code, calibration
records (non-ok rows in full), process/memory state, timing for ETA."""
import _remote as R

SNIPPET = r'''
import json, glob, os, hashlib, subprocess, sys
ROOT = "/root/mk_v2_runs/e3_b9_calib"
P = "/root/mk_v2/src/experiments/external_ports/b9_seeded_fuzzing.py"

print("=== deployed b9 file ===")
src = open(P, encoding="utf-8").read()
print("md5", hashlib.md5(src.encode()).hexdigest(), "bytes", len(src))
print("has QUANTILE_NUMEL_LIMIT:", "QUANTILE_NUMEL_LIMIT" in src)
lines = src.splitlines()
for i, l in enumerate(lines[158:210], start=159):
    print("%4d| %s" % (i, l))

print("=== backups present ===")
for f in sorted(glob.glob("/root/mk_v2/src/experiments/external_ports/b9_seeded_fuzzing.py*")):
    print(f, os.path.getsize(f))

print("=== calibration rows ===")
rows = []
for f in sorted(glob.glob(ROOT + "/calibration_lane*.jsonl")):
    for line in open(f, encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            r["_lane_file"] = os.path.basename(f)
            rows.append(r)
print("total rows", len(rows))
from collections import Counter
print("status counts", dict(Counter(r.get("control_status") for r in rows)))
walls = sorted(r.get("wall_s", 0) for r in rows)
print("wall_s sorted:", [round(w) for w in walls])
import statistics
ok = [r for r in rows if r.get("control_status") in ("calibrated_ok",)]
print("ok wall median", statistics.median([r["wall_s"] for r in ok]) if ok else None,
      "mean", round(statistics.mean([r["wall_s"] for r in ok]), 1) if ok else None,
      "max", max([r["wall_s"] for r in ok]) if ok else None)
print("=== NON-OK ROWS (full) ===")
for r in rows:
    if r.get("control_status") != "calibrated_ok":
        print(json.dumps(r, sort_keys=True))
print("=== ok rows compact ===")
for r in rows:
    if r.get("control_status") == "calibrated_ok":
        print(r["unit"], "rh=%s" % r.get("reduction_heavy"), "tol=%.4g" % r["calibrated_tol"],
              "maxabs=%.4g" % r["control_max_abs"], "wall=%s" % r["wall_s"])

print("=== completed checkpoints ===")
for f in sorted(glob.glob(ROOT + "/completed_lane*.json")):
    print(f, len(json.load(open(f))))

print("=== task table ===")
t = json.load(open(ROOT + "/task_table.json"))
print("keys", list(t.keys()))
print("n tasks", len(t["tasks"]))
nunits = sum(len(x["dtypes"]) for x in t["tasks"])
print("n units total", nunits)
print("reduction_heavy tasks", sum(1 for x in t["tasks"] if x.get("reduction_heavy")))
print("sample task", json.dumps(t["tasks"][0]))

print("=== markers / dir ===")
for f in sorted(os.listdir(ROOT)):
    p = os.path.join(ROOT, f)
    if os.path.isfile(p):
        print(" ", f, os.path.getsize(p))
    else:
        print(" DIR", f, len(os.listdir(p)))

print("=== processes ===")
print(subprocess.run(["bash", "-lc", "ps -eo pid,rss,etimes,args | grep -E 'mutant_worker|guard_b9|_b9_calib_driver|run_e3_external' | grep -v grep"], capture_output=True, text=True).stdout)

print("=== memory / cgroup ===")
for f in ["/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory.events"]:
    try:
        print(f, open(f).read().strip().replace("\n", " | "))
    except OSError as e:
        print(f, "ERR", e)
print(subprocess.run(["bash", "-lc", "free -g; nproc"], capture_output=True, text=True).stdout)

print("=== torch ===")
import torch
print("torch", torch.__version__)
'''

c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/_b9fix_probe1.py", "w") as fh:
    fh.write(SNIPPET)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u /root/_b9fix_probe1.py 2>&1",
      timeout=300)
c.close()
print("PROBE1_DONE")
