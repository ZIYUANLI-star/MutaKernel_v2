"""After EQUIV_DONE: run the six-source merge, build the CSE lane plan, and
launch heavy-serial + dual-light CSE lanes with guard v6."""
import io
import sys
import time

import _remote

ENV_BASE = ("PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
            "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext")
FRACTIONS = {0: "0.92", 1: "0.45", 2: "0.45"}


def lane_cmd(lane):
    return (
        "cd /root/mk_v2 && nohup env " + ENV_BASE +
        f" MK_GPU_MEMORY_FRACTION={FRACTIONS[lane]}"
        " /root/miniconda3/bin/python -u scripts/run_e1_cse_falsify.py"
        " --out-dir /root/mk_v2_runs/e1 --kernelbench-root KernelBench"
        " --timeout 1800"
        " --lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json"
        f" --lane {lane}"
        f" >> /root/mk_v2_runs/e1_cse_lane{lane}.log 2>&1 &"
    )


GUARD_SH = """#!/bin/bash
# E1 CSE guard v6 (2026-07-26): watch CSE lanes 0 (heavy serial, fraction
# 0.92) and 1/2 (light parallel, fraction 0.45 each).  Progress line per
# lane every ~30 minutes; CSE_DONE once all three lanes finish.
RUNS=/root/mk_v2_runs
PIDFILE=$RUNS/e1_cse_guard.pid

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "guard already running ($(cat "$PIDFILE"))"; exit 0
fi
echo $$ > "$PIDFILE"
for L in 0 1 2; do
  echo "[guard $(date '+%F %T %z')] CSE_GUARD_STARTED pid=$$" >> "$RUNS/e1_cse_lane$L.log"
done

CYCLE=0
while true; do
  sleep 120
  CYCLE=$((CYCLE+1))
  for L in 0 1 2; do
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
      FRACTION=0.45
      [ "$L" -eq 0 ] && FRACTION=0.92
      echo "[guard $(date '+%F %T %z')] AUTORESTART cse lane $L: driver missing, relaunching" >> "$LOG"
      cd /root/mk_v2 && nohup env \\
        PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin \\
        TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext \\
        MK_GPU_MEMORY_FRACTION=$FRACTION \\
        /root/miniconda3/bin/python -u scripts/run_e1_cse_falsify.py \\
        --out-dir /root/mk_v2_runs/e1 --kernelbench-root KernelBench \\
        --timeout 1800 \\
        --lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json \\
        --lane $L >> "$LOG" 2>&1 &
    fi
  done
  if [ -f "$RUNS/e1/CSE_DONE_LANE0" ] && [ -f "$RUNS/e1/CSE_DONE_LANE1" ] && [ -f "$RUNS/e1/CSE_DONE_LANE2" ]; then
    touch "$RUNS/e1/CSE_DONE"
    echo "[guard $(date '+%F %T %z')] all CSE lanes done; CSE_DONE written; guard exiting" >> "$RUNS/e1_cse_lane0.log"
    rm -f "$PIDFILE"
    exit 0
  fi
done
"""

c = _remote.connect()

print("===== equiv final state =====")
code, out, _ = _remote.run(c, "ls /root/mk_v2_runs/e1/EQUIV_DONE 2>/dev/null && echo MARKER_PRESENT || echo NOT_DONE", timeout=30)
if "MARKER_PRESENT" not in out:
    print("ABORT: EQUIV_DONE not present")
    sys.exit(1)
_remote.run(c, "tail -n 4 /root/mk_v2_runs/e1_equiv_lane4_requeue.log", timeout=30)

print("===== six-source merge =====")
code, out, err = _remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _e1_merge_lanes_remote.py", timeout=300)
if "MERGE_OK" not in out:
    print("ABORT: merge failed, not starting CSE")
    sys.exit(1)

print("===== CSE lane plan =====")
code, out, err = _remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python _e1_cse_plan_remote.py", timeout=300)
if "CSE_PLAN_OK" not in out:
    print("ABORT: cse plan failed")
    sys.exit(1)

sftp = c.open_sftp()
sftp.putfo(io.BytesIO(GUARD_SH.replace("\r\n", "\n").encode()),
           "/root/mk_v2_runs/e1_cse_guard.sh")
sftp.close()
_remote.run(c, "chmod +x /root/mk_v2_runs/e1_cse_guard.sh && rm -f /root/mk_v2_runs/e1_cse_guard.pid", timeout=20)

for lane in (0, 1, 2):
    print(f"===== start cse lane {lane} =====")
    try:
        _remote.run(c, lane_cmd(lane) + f" echo CSE{lane}_LAUNCHED", timeout=15)
    except Exception as exc:
        print(f"cse lane {lane} launch (tolerated):", type(exc).__name__)
    time.sleep(3)

print("===== start cse guard =====")
try:
    _remote.run(c, "nohup bash /root/mk_v2_runs/e1_cse_guard.sh > /dev/null 2>&1 & echo CSE_GUARD_LAUNCHED", timeout=15)
except Exception as exc:
    print("guard launch (tolerated):", type(exc).__name__)

time.sleep(25)
print("===== verify =====")
_remote.run(c, "date '+%F %T %z'; ps -eo pid,args | awk '/run_e1_cse_falsify|e1_cse_guard/ && !/awk/ {print $1, $(NF-1), $NF}'", timeout=30)
for lane in (0, 1, 2):
    _remote.run(c, f"tail -n 2 /root/mk_v2_runs/e1_cse_lane{lane}.log", timeout=30)
c.close()
print("CSE_GO_DONE")
