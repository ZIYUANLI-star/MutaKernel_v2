"""Stop lanes 2/3, move out timeout INCONCLUSIVEs, start the serial requeue.

Retry regime: single process, MK_GPU_MEMORY_FRACTION=0.9, --timeout 1800,
round watchdog unchanged (90s).  Output files carry the lane4_requeue
suffix so local monitoring globs (e1_equiv_lane*.log /
equiv_observations_lane*.jsonl) keep matching.
"""
import io
import re
import time

import _remote

RETRY_CMD = (
    "cd /root/mk_v2 && nohup env "
    "PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
    "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
    "MK_GPU_MEMORY_FRACTION=0.9 "
    "/root/miniconda3/bin/python -u scripts/run_e1_probe_study.py "
    "--phase equiv --kernelbench-root KernelBench "
    "--out-dir /root/mk_v2_runs/e1 --timeout 1800 "
    "--lane-plan /root/mk_v2_runs/e1/lane_plan.json "
    "--lane 4 --lane-tag requeue "
    ">> /root/mk_v2_runs/e1_equiv_lane4_requeue.log 2>&1 &"
)

GUARD_SH = """#!/bin/bash
# E1 equiv guard v5 (2026-07-25): watch the serial requeue driver (lane 4,
# tag requeue).  Emits a progress line every ~30 minutes for the local
# watcher; writes EQUIV_DONE when the requeue lane finishes.
RUNS=/root/mk_v2_runs
LOG=$RUNS/e1_equiv_lane4_requeue.log
OBS=$RUNS/e1/equiv_observations_lane4_requeue.jsonl
PIDFILE=$RUNS/e1_guard.pid

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "guard already running ($(cat "$PIDFILE"))"; exit 0
fi
echo $$ > "$PIDFILE"
echo "[guard $(date '+%F %T %z')] GUARD_STARTED (requeue lane 4) pid=$$" >> "$LOG"

CYCLE=0
while true; do
  sleep 120
  CYCLE=$((CYCLE+1))
  if [ $((CYCLE % 15)) -eq 0 ]; then
    N=$(wc -l < "$OBS" 2>/dev/null || echo 0)
    I=$(grep -c '"evidence_grade": "INCONCLUSIVE"' "$OBS" 2>/dev/null || echo 0)
    echo "[guard progress $(date '+%F %T %z')] requeue obs=$N inconclusive=$I" >> "$LOG"
  fi
  if grep -q 'equiv DONE' "$LOG"; then
    touch "$RUNS/e1/EQUIV_DONE_LANE4" "$RUNS/e1/EQUIV_DONE"
    echo "[guard $(date '+%F %T %z')] requeue lane done; EQUIV_DONE written; guard exiting" >> "$LOG"
    rm -f "$PIDFILE"
    exit 0
  fi
  if ! pgrep -f "run_e1_probe_study.py.*--lane-tag requeue\\$" > /dev/null; then
    echo "[guard $(date '+%F %T %z')] AUTORESTART lane 4/requeue: driver missing, relaunching" >> "$LOG"
    cd /root/mk_v2 && nohup env \\
      PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin \\
      TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext \\
      MK_GPU_MEMORY_FRACTION=0.9 \\
      /root/miniconda3/bin/python -u scripts/run_e1_probe_study.py \\
      --phase equiv --kernelbench-root KernelBench \\
      --out-dir /root/mk_v2_runs/e1 --timeout 1800 \\
      --lane-plan /root/mk_v2_runs/e1/lane_plan.json \\
      --lane 4 --lane-tag requeue >> "$LOG" 2>&1 &
  fi
done
"""

FILES = [
    ("scripts/run_e1_probe_study.py", "/root/mk_v2/scripts/run_e1_probe_study.py"),
    ("tests/test_e1_lane_partition.py", "/root/mk_v2/tests/test_e1_lane_partition.py"),
    ("_e1_requeue_timeout_remote.py", "/root/mk_v2/_e1_requeue_timeout_remote.py"),
    ("_e1_merge_lanes_remote.py", "/root/mk_v2/_e1_merge_lanes_remote.py"),
]

c = _remote.connect()
sftp = c.open_sftp()
for local, remote in FILES:
    sftp.put(local, remote)
    print("PUT", local)
sftp.putfo(io.BytesIO(GUARD_SH.replace("\r\n", "\n").encode()),
           "/root/mk_v2_runs/e1_guard_v5.sh")
sftp.close()

print("===== remote pytest =====")
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -m pytest tests -x -q 2>&1 | tail -3", timeout=1500)

print("===== T0: stop guard =====")
_remote.run(c, "date '+%F %T %z'; GP=$(cat /root/mk_v2_runs/e1_guard.pid 2>/dev/null); "
               "echo guard_pid: $GP; kill $GP 2>/dev/null; rm -f /root/mk_v2_runs/e1_guard.pid; "
               "sleep 1; ps -p $GP > /dev/null 2>&1 && echo GUARD_STILL_ALIVE || echo GUARD_STOPPED",
            timeout=30)

print("===== locate lanes 2/3 =====")
_, out, _ = _remote.run(c, "ps -eo pid,ppid,args", timeout=30, echo=False)
targets = []
for line in out.splitlines():
    if ("run_e1_probe_study.py" in line and "python" in line
            and ("--lane 2" in line or "--lane 3" in line)):
        pid = int(line.split()[0])
        targets.append(pid)
        print("driver:", line.strip()[:110])
for line in out.splitlines():
    if "_mutant_worker.py" in line:
        parts = line.split()
        if int(parts[1]) in targets:
            targets.append(int(parts[0]))
            print("worker:", line.strip()[:110])
if len([t for t in targets]) < 2:
    raise SystemExit("ABORT: expected lane2/3 drivers, found " + str(targets))

print("===== kill by PID =====")
_remote.run(c, f"kill -9 {' '.join(map(str, targets))} 2>/dev/null; sleep 2; "
               "ps -eo pid,args | grep -E 'run_e1|_mutant_worker' | grep -v grep || echo LANES23_STOPPED",
            timeout=30)

print("===== moveout (extended timeout filter) =====")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _e1_requeue_timeout_remote.py", timeout=120)

print("===== install guard v5, start retry =====")
_remote.run(c, "cp /root/mk_v2_runs/e1_guard_v5.sh /root/mk_v2_runs/e1_guard.sh && chmod +x /root/mk_v2_runs/e1_guard.sh", timeout=20)
try:
    _remote.run(c, RETRY_CMD + " echo RETRY_LAUNCHED", timeout=15)
except Exception as exc:
    print("retry launch (tolerated):", type(exc).__name__)
time.sleep(3)
try:
    _remote.run(c, "nohup bash /root/mk_v2_runs/e1_guard.sh > /dev/null 2>&1 & echo GUARD_LAUNCHED", timeout=15)
except Exception as exc:
    print("guard launch (tolerated):", type(exc).__name__)

time.sleep(20)
print("===== verify =====")
_remote.run(c, "date '+%F %T %z'; ps -eo pid,args | awk '/run_e1_probe_study|e1_guard/ && !/awk/ {print $1, $(NF-2), $(NF-1), $NF}'", timeout=30)
_remote.run(c, "tail -n 3 /root/mk_v2_runs/e1_equiv_lane4_requeue.log", timeout=30)
c.close()
print("SWITCH_REQUEUE_DONE")
