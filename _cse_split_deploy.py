"""Deploy the split: upload code + plan + go-script + guard v2, run remote
tests, generate the split plan, and report current CSE progress."""
import io

import _remote

GUARD_SH = """#!/bin/bash
# E1 CSE guard v7 (split): watch lanes 3 (heavy-serial 0.92) and 4/5
# (proven-safe parallel, 0.45 each; 0.45+0.45 <= 0.92 red line).
# Lanes 1/2 already carry CSE_DONE markers; CSE_DONE when 3/4/5 all finish.
RUNS=/root/mk_v2_runs
PIDFILE=$RUNS/e1_guard.pid

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "guard already running ($(cat "$PIDFILE"))"; exit 0
fi
echo $$ > "$PIDFILE"
for L in 3 4 5; do
  echo "[guard $(date '+%F %T %z')] GUARD_STARTED (CSE split lanes 3/4/5) pid=$$" >> "$RUNS/e1_cse_lane$L.log"
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
        --timeout 1800 --lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json \\
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

FILES = [
    ("scripts/run_e1_cse_falsify.py", "/root/mk_v2/scripts/run_e1_cse_falsify.py"),
    ("tests/test_e1_cse_lanes.py", "/root/mk_v2/tests/test_e1_cse_lanes.py"),
    ("_cse_split_plan_remote.py", "/root/mk_v2/_cse_split_plan_remote.py"),
    ("_cse_split_go_remote.py", "/root/mk_v2/_cse_split_go.py"),
]

c = _remote.connect()
sftp = c.open_sftp()
for local, remote in FILES:
    sftp.put(local, remote)
    print("PUT", local, "->", remote)
sftp.putfo(io.BytesIO(GUARD_SH.replace("\r\n", "\n").encode()),
           "/root/mk_v2_runs/e1_guard_cse_split.sh")
print("PUT guard v7 -> /root/mk_v2_runs/e1_guard_cse_split.sh")
sftp.close()

print("===== remote pytest =====")
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -m pytest tests -x -q 2>&1 | tail -3", timeout=1500)
print("===== split plan =====")
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python _cse_split_plan_remote.py", timeout=300)
print("===== current CSE progress =====")
_remote.run(c, "date '+%F %T %z'; ls /root/mk_v2_runs/e1/CSE_DONE* 2>/dev/null || echo NO_MARKERS_YET; "
               "for L in 0 1 2; do echo -n \"lane$L obs: \"; wc -l < /root/mk_v2_runs/e1/cse_observations_lane$L.jsonl 2>/dev/null || echo 0; done; "
               "tail -n 1 /root/mk_v2_runs/e1_cse_lane1.log; tail -n 1 /root/mk_v2_runs/e1_cse_lane2.log",
            timeout=60)
c.close()
print("SPLIT_DEPLOY_DONE")
