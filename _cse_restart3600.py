"""Restart CSE lanes 3/4/5 with --timeout 3600 + guard v8 (3600 in restarts).

Budget basis: heaviest serial kernel equiv median 1044s x 3.22 round ratio
~= 3360s < 3600; heaviest parallel (proven-safe) ~900s x 3.22 x 1.1
contention ~= 3200s < 3600.  Partial-evidence grading backstops overruns.
"""
import io
import time

import _remote

GUARD_SH = """#!/bin/bash
# E1 CSE guard v8 (2026-07-27): lanes 3/4/5, 3600s probe budget,
# partial-evidence backstop in the driver.
RUNS=/root/mk_v2_runs
PIDFILE=$RUNS/e1_guard.pid

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "guard already running ($(cat "$PIDFILE"))"; exit 0
fi
echo $$ > "$PIDFILE"
for L in 3 4 5; do
  echo "[guard $(date '+%F %T %z')] GUARD_STARTED (v8, 3600s budget) pid=$$" >> "$RUNS/e1_cse_lane$L.log"
done

CYCLE=0
while true; do
  sleep 120
  CYCLE=$((CYCLE+1))
  for L in 3 4 5; do
    LOG=$RUNS/e1_cse_lane$L.log
    OBS=$RUNS/e1/cse_observations_lane$L.jsonl
    MARK=$RUNS/e1/CSE_DONE_LANE$L
    if [ -f "$MARK" ]; then continue; fi
    if [ $((CYCLE % 15)) -eq 0 ]; then
      N=$(wc -l < "$OBS" 2>/dev/null || echo 0)
      echo "[guard progress $(date '+%F %T %z')] cse lane $L obs=$N" >> "$LOG"
    fi
    if grep -q 'cse-falsify DONE' "$LOG"; then
      touch "$MARK"
      echo "[guard $(date '+%F %T %z')] cse lane $L DONE marker written" >> "$LOG"
      continue
    fi
    if ! pgrep -f "run_e1_cse_falsify.py.*--lane $L\\$" > /dev/null; then
      if [ "$L" = "3" ]; then FRAC=0.92; else FRAC=0.45; fi
      echo "[guard $(date '+%F %T %z')] AUTORESTART cse lane $L: driver missing, relaunching" >> "$LOG"
      cd /root/mk_v2 && nohup env \\
        PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin \\
        TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext \\
        MK_GPU_MEMORY_FRACTION=$FRAC \\
        /root/miniconda3/bin/python -u scripts/run_e1_cse_falsify.py \\
        --out-dir /root/mk_v2_runs/e1 --kernelbench-root KernelBench \\
        --timeout 3600 --lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json \\
        --lane $L >> "$LOG" 2>&1 &
    fi
  done
  if [ -f "$RUNS/e1/CSE_DONE_LANE3" ] && [ -f "$RUNS/e1/CSE_DONE_LANE4" ] && [ -f "$RUNS/e1/CSE_DONE_LANE5" ]; then
    touch "$RUNS/e1/CSE_DONE"
    echo "[guard $(date '+%F %T %z')] split lanes done; CSE_DONE written; guard exiting" >> "$RUNS/e1_cse_lane3.log"
    rm -f "$PIDFILE"
    exit 0
  fi
done
"""

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(GUARD_SH.replace("\r\n", "\n").encode()),
           "/root/mk_v2_runs/e1_guard.sh")
sftp.close()
_remote.run(c, "chmod +x /root/mk_v2_runs/e1_guard.sh; rm -f /root/mk_v2_runs/e1_guard.pid", timeout=20)

for lane, frac in ((3, 0.92), (4, 0.45), (5, 0.45)):
    cmd = (
        "cd /root/mk_v2 && nohup env "
        "PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
        "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
        f"MK_GPU_MEMORY_FRACTION={frac} "
        "/root/miniconda3/bin/python -u scripts/run_e1_cse_falsify.py "
        "--out-dir /root/mk_v2_runs/e1 --kernelbench-root KernelBench "
        "--timeout 3600 --lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json "
        f"--lane {lane} >> /root/mk_v2_runs/e1_cse_lane{lane}.log 2>&1 & echo L{lane}_UP"
    )
    try:
        _remote.run(c, cmd, timeout=15)
    except Exception as exc:
        print(f"lane {lane} (tolerated):", type(exc).__name__)
    time.sleep(3)
try:
    _remote.run(c, "nohup bash /root/mk_v2_runs/e1_guard.sh > /dev/null 2>&1 & echo GUARD_UP", timeout=15)
except Exception as exc:
    print("guard (tolerated):", type(exc).__name__)

time.sleep(25)
print("===== verify =====")
_remote.run(c, "date '+%F %T %z'; ps -eo pid,args | awk '/run_e1_cse_falsify.py --out/ && !/awk/ {n++; print $1, $(NF-1), $NF} END {print \"drivers:\", n}'; "
               "cat /root/mk_v2_runs/e1_guard.pid", timeout=30)
for lane in (3, 4, 5):
    _remote.run(c, f"tail -n 1 /root/mk_v2_runs/e1_cse_lane{lane}.log", timeout=30)
c.close()
print("RESTART3600_DONE")
