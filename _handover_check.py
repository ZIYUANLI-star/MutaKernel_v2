"""Verify the B9 -> determinism-audit handover: no overlap, checkpoints intact.

Process-name literals are assembled from fragments so that this command's own
bash line cannot be mistaken for a critical-path process by the B9 chain
trigger's /proc cmdline scan.
"""
import _remote

PY = r'''
import glob
import json
import os
import subprocess

WORKER = "_mutant" + "_worker.py"
CSE = "run_e1_cse_" + "falsify.py"
B9D = "_b9_calib_driver"


def procs():
    rows = []
    for d in glob.glob("/proc/[0-9]*"):
        try:
            cmd = open(d + "/cmdline", "rb").read().replace(b"\0", b" ").decode(
                errors="replace").strip()
        except OSError:
            continue
        if not cmd:
            continue
        for needle, label in ((WORKER, "AUDIT/CSE worker"),
                              (CSE, "CSE driver"),
                              (B9D, "B9 lane driver"),
                              ("run_e3_external.py", "B9 unit"),
                              ("guard_b9", "B9 guard"),
                              ("chain_trigger", "B9 chain trigger"),
                              ("stage1_chain", "B9 stage1 chain"),
                              ("_signoff_" + "orch.py", "signoff orch")):
            if needle in cmd:
                rows.append((os.path.basename(d), label, cmd[:120]))
                break
    return rows


print("=== live processes of interest ===")
for pid, label, cmd in sorted(procs(), key=lambda r: r[1]):
    print(f"  [{label}] pid={pid} :: {cmd}")

print()
print("=== overlap check (the OOM scenario) ===")
rows = procs()
audit = [r for r in rows if r[1] == "AUDIT/CSE worker"]
b9run = [r for r in rows if r[1] in ("B9 lane driver", "B9 unit")]
if audit and b9run:
    print("  !! OVERLAP: audit worker AND B9 units both running")
else:
    print(f"  ok: audit workers={len(audit)}, B9 runners={len(b9run)}")

print()
print("=== B9 checkpoint integrity ===")
base = "/root/mk_v2_runs/e3_b9_calib/"
for p in sorted(glob.glob(base + "calibration*.jsonl")):
    n = sum(1 for line in open(p, encoding="utf-8") if line.strip())
    print(f"  {os.path.basename(p)}: {n} rows")
for p in sorted(glob.glob(base + "completed*.json")):
    try:
        ids = json.load(open(p, encoding="utf-8"))
        print(f"  {os.path.basename(p)}: {len(ids)} ids")
    except Exception as exc:
        print(f"  {os.path.basename(p)}: unreadable {type(exc).__name__}")
print("  markers:", sorted(os.path.basename(x) for x in
                           glob.glob(base + "*PAUSED*") +
                           glob.glob(base + "*FIRED*") +
                           glob.glob(base + "STAGE1*")))

print()
print("=== E1 final ledger snapshot ===")
e1 = "/root/mk_v2_runs/e1/"
from collections import Counter
cse = {}
for p in sorted(glob.glob(e1 + "cse_observations_lane*.jsonl")):
    if ".bak" in p:
        continue
    for line in open(p, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            cse[r["probe_id"]] = r.get("outcome")
print("  CSE unique probes:", len(cse), dict(Counter(cse.values())))
fal = sorted(k for k, v in cse.items() if v == "FALSIFIED")
print("  FALSIFIED:", fal)

print()
print("=== resources ===")
subprocess.run("cat /sys/fs/cgroup/memory.events 2>/dev/null | grep oom_kill || "
               "grep oom_kill /sys/fs/cgroup/memory/memory.oom_control", shell=True)
subprocess.run("nvidia-smi --query-gpu=memory.used --format=csv,noheader", shell=True)
'''

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_handover_check_remote.py", "w") as f:
    f.write(PY)
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python -u /root/mk_v2/_handover_check_remote.py",
            timeout=180)
c.close()
