"""Deploy the self-healing sentinel: upload, compile-check, run the sandbox
drill, pre-scan real data (abort if a rule would fire surgery immediately at
startup), then nohup-start the sentinel and verify liveness + heartbeat #1."""
import io
import time

import _remote

PRESCAN = r"""
import json, os, time
from pathlib import Path
RUNS = Path("/root/mk_v2_runs"); E1 = RUNS / "e1"
now = time.time()
bad_total = 0
for L in (3, 4, 5):
    p = E1 / f"cse_observations_lane{L}.jsonl"
    recs = []
    if p.exists():
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try: recs.append(json.loads(ln))
            except ValueError: pass
    inc = sum(1 for r in recs if r.get("outcome") == "INCONCLUSIVE")
    tinc = sum(1 for r in recs if r.get("outcome") == "INCONCLUSIVE"
               and (r.get("timed_out") or r.get("inconclusive_class") == "timeout"))
    fals = [r for r in recs if r.get("outcome") == "FALSIFIED"]
    bad = [r["probe_id"] for r in fals
           if any(r.get(k) in (None, "") for k in
                  ("witness_policy", "witness_round", "witness_seed"))]
    bad_total += len(bad)
    age = round(now - p.stat().st_mtime) if p.exists() else None
    done = (E1 / f"CSE_DONE_LANE{L}").exists()
    print(f"lane{L}: obs={len(recs)} inc={inc} timeout_inc={tinc} "
          f"falsified={len(fals)} bad_witness={bad} obs_age_s={age} done={done}")
print("BAD_WITNESS_TOTAL=%d" % bad_total)
try:
    pid = int((RUNS / "e1_guard.pid").read_text().strip())
    alive = Path(f"/proc/{pid}").exists()
except Exception:
    pid, alive = None, False
print(f"guard: pid={pid} alive={alive}")
print("PRESCAN_DONE")
"""

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_e1_sentinel_remote.py", "/root/mk_v2/e1_sentinel.py")
sftp.put("_e1_sentinel_drill_remote.py", "/root/mk_v2/e1_sentinel_drill.py")
sftp.putfo(io.BytesIO(PRESCAN.encode()), "/root/mk_v2/_sentinel_prescan.py")
print("PUT sentinel + drill + prescan")
sftp.close()

print("===== compile check =====")
code, _, _ = _remote.run(
    c, "/root/miniconda3/bin/python -m py_compile /root/mk_v2/e1_sentinel.py "
       "/root/mk_v2/e1_sentinel_drill.py && echo COMPILE_OK", timeout=60)
if code != 0:
    raise SystemExit("ABORT: compile failed")

print("===== sandbox drill =====")
code, out, _ = _remote.run(
    c, "cd /root/mk_v2 && /root/miniconda3/bin/python e1_sentinel_drill.py",
    timeout=300)
if "DRILL_ALL_PASS" not in out:
    raise SystemExit("ABORT: drill failed")

print("===== real-data prescan =====")
code, out, _ = _remote.run(
    c, "/root/miniconda3/bin/python /root/mk_v2/_sentinel_prescan.py",
    timeout=120)
if "BAD_WITNESS_TOTAL=0" not in out:
    raise SystemExit("ABORT: existing bad-witness records; human review first")

print("===== start sentinel =====")
try:
    _remote.run(c, "cd /root/mk_v2 && nohup /root/miniconda3/bin/python -u "
                   "e1_sentinel.py >> /root/mk_v2_runs/e1_sentinel.log 2>&1 "
                   "& echo SENTINEL_UP", timeout=15)
except Exception as exc:
    print("start (tolerated):", type(exc).__name__)

time.sleep(25)
print("===== verify liveness + heartbeat #1 =====")
_remote.run(c, "PID=$(cat /root/mk_v2_runs/e1_sentinel.pid 2>/dev/null); "
               "echo sentinel_pid=$PID; ls /proc/$PID/cmdline >/dev/null 2>&1 "
               "&& echo SENTINEL_ALIVE || echo SENTINEL_DEAD; "
               "tail -n 5 /root/mk_v2_runs/e1_sentinel.log; "
               "echo ---heartbeat---; "
               "tail -n 1 /root/mk_v2_runs/sentinel_heartbeat.jsonl",
            timeout=30)
c.close()
print("SENTINEL_DEPLOY_DONE")
