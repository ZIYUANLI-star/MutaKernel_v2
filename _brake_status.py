"""Check brake holders, audit liveness, and B9 progress.

Needle literals are split so this command's own shell line is not mistaken for
a critical-path process by the brake supervisor's /proc scan.
"""
import _remote

PY = r'''
import glob
import json
import os
import subprocess

WORKER = "_mutant" + "_worker.py"
b9 = "/root/mk_v2_runs/e3_b9_calib/"

print("=== brake state ===")
r = subprocess.run(["/root/miniconda3/bin/python", "/root/mk_v2/_b9_brake.py", "status"],
                   capture_output=True, text=True)
print((r.stdout or "").strip() or "(no output)")
if r.stderr.strip():
    print("stderr:", r.stderr.strip()[:400])
print("brake dir:", sorted(os.path.basename(p) for p in glob.glob(b9 + "brakes/*")))
print("legacy marker:", os.path.exists(b9 + "PAUSED_FOR_SIGNOFF_RERUN"))

print()
print("=== audit liveness ===")
alive = []
for d in glob.glob("/proc/[0-9]*"):
    try:
        cmd = open(d + "/cmdline", "rb").read().replace(b"\0", b" ").decode(
            errors="replace")
    except OSError:
        continue
    if WORKER in cmd or "WC_AUDIT" in cmd:
        alive.append((os.path.basename(d), cmd[:130]))
for pid, cmd in alive:
    print(f"  pid={pid} :: {cmd}")
print("  audit workers alive:", len(alive))

wc = "/root/mk_v2_runs/e1/witness_confirmation/"
if os.path.isdir(wc):
    files = sorted(glob.glob(wc + "*.json") + glob.glob(wc + "*.jsonl"))
    print("  outputs:", [os.path.basename(f) for f in files])
    for f in files:
        if "report" in os.path.basename(f):
            try:
                d = json.load(open(f, encoding="utf-8"))
                print(f"  -- {os.path.basename(f)}:",
                      json.dumps(d, ensure_ascii=False)[:700])
            except Exception as exc:
                print(f"  -- {os.path.basename(f)}: {type(exc).__name__}")
    logs = sorted(glob.glob(wc + "*.log"))
    for lg in logs[:2]:
        print(f"  tail {os.path.basename(lg)}:")
        os.system(f"tail -4 {lg}")

print()
print("=== B9 progress ===")
try:
    qs = json.load(open(b9 + "queue_state.json", encoding="utf-8"))
    print("  pending:", len(qs.get("pending", [])),
          "claimed:", qs.get("claimed"),
          "done:", len(qs.get("done", [])),
          "stage2_deferred:", len(qs.get("stage2_deferred", [])))
except Exception as exc:
    print("  queue_state unreadable:", type(exc).__name__)
for p in sorted(glob.glob(b9 + "calibration_v2_lane*.jsonl")):
    n = sum(1 for x in open(p, encoding="utf-8") if x.strip())
    print(f"  {os.path.basename(p)}: {n}")
print("  gate report:", os.path.exists(b9 + "STAGE1_GATE_REPORT.json"))

print()
print("=== resources ===")
subprocess.run("grep oom_kill /sys/fs/cgroup/memory.events", shell=True)
subprocess.run("nvidia-smi --query-gpu=memory.used --format=csv,noheader", shell=True)
'''

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_brake_status_remote.py", "w") as f:
    f.write(PY)
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python -u /root/mk_v2/_brake_status_remote.py",
            timeout=180)
c.close()
