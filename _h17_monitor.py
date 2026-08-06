"""B9 first-wave monitor: critical path, trigger state, per-unit results, memory."""
import io
import sys

import _remote

SCRIPT = r'''
import json, sys, collections
from pathlib import Path
sys.path.insert(0, "/root/mk_v2")

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
E1 = Path("/root/mk_v2_runs/e1")
import _b9_chain_trigger as t

def oom_count():
    for p in ("/sys/fs/cgroup/memory.events",
              "/sys/fs/cgroup/memory/memory.oom_control"):
        try:
            for line in open(p, encoding="utf-8"):
                if line.startswith("oom_kill "):
                    return int(line.split()[1])
        except OSError:
            continue
    return None

import time
print("=== %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
print("[critical path]")
print("  SIGNOFF_ORCH_DONE:", (E1 / "SIGNOFF_ORCH_DONE").is_file())
procs = t.critical_path_processes()
for needle, pid, cl in procs:
    print("   %-24s pid=%-7d %s" % (needle, pid, cl[:100]))
if not procs:
    print("   (no critical-path process)")
sc = E1 / "cse_completed_lane3_signoff_requeue.json"
if sc.is_file():
    done = json.loads(sc.read_text())
    print("  signoff probes done: %d/6 %s" % (len(done), done))

print("[chain trigger]")
print("  fired:", (OUT / "CHAIN_TRIGGER_FIRED").is_file(),
      " exited:", (OUT / "CHAIN_TRIGGER_EXIT").is_file(),
      " paused marker:", t.PAUSE_MARKER.is_file())
print("  trigger procs:", [p for p, _ in t.find_processes("_b9_chain_trigger.py")])
log = OUT / "chain_trigger.log"
if log.is_file():
    lines = log.read_text().splitlines()
    print("  log tail:")
    for line in lines[-6:]:
        print("   ", line[:190])

print("[b9 runtime]")
print("  b9 procs:", [(n, p) for n, p, _ in t.b9_processes()])
print("  oom_kill (cgroup, baseline 20):", oom_count())
print("  gpu:", t.gpu_compute_apps())
try:
    lim = int(open("/sys/fs/cgroup/memory/memory.limit_in_bytes").read()) / 2**30
    use = int(open("/sys/fs/cgroup/memory/memory.usage_in_bytes").read()) / 2**30
    print("  cgroup mem: %.1f / %.1f GiB" % (use, lim))
except OSError:
    pass

st = OUT / "queue_state.json"
if st.is_file():
    s = json.loads(st.read_text())
    print("[queue] pending=%d claimed=%d done=%d"
          % (len(s["pending"]), len(s["claimed"]), len(s["done"])))
    for uid, cl in s["claimed"].items():
        print("   in flight: %-22s lane=%s pid=%s since=%s reserve=%.1f GiB"
              % (uid, cl["lane"], cl["pid"], cl["since"], cl["reserve_gb"]))
    if s["pending"]:
        print("   next up:", s["pending"][:6])

print("[wave v2 results]")
rows = []
for p in sorted(OUT.glob("calibration_v2_lane*.jsonl")):
    for line in p.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
if not rows:
    print("  (no v2 rows yet)")
else:
    cnt = collections.Counter(r["control_status"] for r in rows)
    print("  %d rows: %s" % (len(rows), dict(cnt)))
    hdr = "  %-22s %-22s %5s %8s %9s %9s %6s %s"
    print(hdr % ("unit", "status", "exit", "wall_s", "est_peak", "peak_rss",
                 "ratio", "tol"))
    for r in rows:
        est = r.get("est_peak_gb") or 0
        act = r.get("unit_peak_rss_gb") or 0
        ratio = (act / est) if est else float("nan")
        print(hdr % (r["unit"], r["control_status"], str(r.get("exit_code")),
                     "%.0f" % (r.get("wall_s") or 0), "%.1f GB" % est,
                     "%.1f GB" % act, "%.2f" % ratio,
                     str(r.get("calibrated_tol"))))
    ok = [r for r in rows if r.get("unit_peak_rss_gb") and r.get("est_peak_gb")]
    if ok:
        rs = [r["unit_peak_rss_gb"] / r["est_peak_gb"] for r in ok]
        print("  memory model actual/estimate: n=%d min=%.2f median=%.2f max=%.2f"
              % (len(rs), min(rs), sorted(rs)[len(rs)//2], max(rs)))
for name in ("lane_v2_0.log", "lane_v2_1.log", "guard_b9_v2.log"):
    p = OUT / name
    if p.is_file():
        tail = p.read_text().splitlines()[-4:]
        print("[%s]" % name)
        for line in tail:
            print("   ", line[:180])
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_b9_monitor.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_b9_monitor.py", timeout=300)
c.close()
