"""Assess the orphaned witness-confirmation audit so it can be taken over."""
import _remote

PY = r'''
import glob
import json
import os
import subprocess

WORKER = "_mutant" + "_worker.py"
wc = "/root/mk_v2_runs/e1/witness_confirmation/"

print("=== audit driver / worker processes ===")
rows = []
for d in glob.glob("/proc/[0-9]*"):
    try:
        cmd = open(d + "/cmdline", "rb").read().replace(b"\0", b" ").decode(
            errors="replace").strip()
        stat = open(d + "/stat").read().split()
        ppid = stat[3]
    except (OSError, IndexError):
        continue
    if not cmd:
        continue
    if any(k in cmd for k in ("wc_audit", "witness_confirmation", "WC_AUDIT",
                              WORKER, "_wc_", "audit_lane")):
        rows.append((int(os.path.basename(d)), ppid, cmd[:150]))
for pid, ppid, cmd in sorted(rows):
    print(f"  pid={pid} ppid={ppid} :: {cmd}")
print("  total:", len(rows))

print()
print("=== audit driver scripts on disk ===")
for pat in ("/root/mk_v2/_*wc*.py", "/root/mk_v2/_*witness*.py",
            "/root/mk_v2/_*audit*.py", wc + "*.sh"):
    for p in sorted(glob.glob(pat)):
        print(f"  {p} ({os.path.getsize(p)} B)")

print()
print("=== audit outputs ===")
for p in sorted(glob.glob(wc + "*")):
    if os.path.isfile(p):
        print(f"  {os.path.basename(p)} ({os.path.getsize(p)} B)")
    else:
        n = len(glob.glob(p + "/*"))
        print(f"  {os.path.basename(p)}/ ({n} entries)")

print()
print("=== progress from lane logs ===")
for lg in sorted(glob.glob(wc + "*.log")):
    print(f"-- {os.path.basename(lg)}")
    os.system(f"tail -3 {lg}")

print()
print("=== cell result files ===")
cells = glob.glob(wc + "cells/*.json") + glob.glob(wc + "*cells*/*.json")
print("  cell json count:", len(cells))
for p in sorted(glob.glob(wc + "*.jsonl")):
    n = sum(1 for x in open(p, encoding="utf-8") if x.strip())
    print(f"  {os.path.basename(p)}: {n} rows")

print()
print("=== wc1_report summary ===")
rp = wc + "wc1_report.json"
if os.path.exists(rp):
    d = json.load(open(rp, encoding="utf-8"))
    print("  generated_at:", d.get("generated_at"))
    print("  cells_done/planned:", d.get("cells_done"), "/", d.get("cells_planned"))
    print("  control_cell_states:", d.get("control_cell_states"))
    kd = d.get("kernel_determinism") or {}
    print("  kernels tracked:", len(kd))
    nd = [k for k, v in kd.items() if v.get("nondeterministic")]
    inc = [k for k, v in kd.items() if v.get("status") != "complete"]
    print("  flagged nondeterministic:", nd)
    print("  incomplete kernels:", len(inc))

print()
print("=== resources ===")
subprocess.run("cat /sys/fs/cgroup/memory.events | grep oom_kill", shell=True)
subprocess.run("nvidia-smi --query-gpu=memory.used --format=csv,noheader", shell=True)
'''

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_audit_takeover_remote.py", "w") as f:
    f.write(PY)
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python -u /root/mk_v2/_audit_takeover_remote.py",
            timeout=180)
c.close()
