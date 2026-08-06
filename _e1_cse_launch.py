"""Launch the three CSE lanes (heavy-serial 0.92 + light x2 at 0.45) and
guard v6.  Also starts a 40-minute GPU memory sampler."""
import io
import time

import _remote


def lane_cmd(lane, fraction):
    return (
        "cd /root/mk_v2 && nohup env "
        "PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
        "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
        f"MK_GPU_MEMORY_FRACTION={fraction} "
        "/root/miniconda3/bin/python -u scripts/run_e1_cse_falsify.py "
        "--out-dir /root/mk_v2_runs/e1 --kernelbench-root KernelBench "
        "--timeout 1800 "
        "--lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json "
        f"--lane {lane} "
        f">> /root/mk_v2_runs/e1_cse_lane{lane}.log 2>&1 &"
    )


GUARD_SH = """#!/bin/bash
# E1 CSE guard v6 (2026-07-26): watch the three CSE lanes (0=heavy-serial
# fraction 0.92, 1/2=light-parallel fraction 0.45).  Progress line per lane
# every ~30 min; CSE_DONE when all three lanes finish.
RUNS=/root/mk_v2_runs
PIDFILE=$RUNS/e1_guard.pid

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "guard already running ($(cat "$PIDFILE"))"; exit 0
fi
echo $$ > "$PIDFILE"
for L in 0 1 2; do
  echo "[guard $(date '+%F %T %z')] GUARD_STARTED (CSE lanes 0/1/2) pid=$$" >> "$RUNS/e1_cse_lane$L.log"
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
      if [ "$L" = "0" ]; then FRAC=0.92; else FRAC=0.45; fi
      echo "[guard $(date '+%F %T %z')] AUTORESTART cse lane $L: driver missing, relaunching" >> "$LOG"
      cd /root/mk_v2 && nohup env \\
        PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin \\
        TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext \\
        MK_GPU_MEMORY_FRACTION=$FRAC \\
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
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(GUARD_SH.replace("\r\n", "\n").encode()),
           "/root/mk_v2_runs/e1_guard.sh")
sftp.close()
_remote.run(c, "chmod +x /root/mk_v2_runs/e1_guard.sh; rm -f /root/mk_v2_runs/e1_guard.pid; "
               "ps -eo args | grep -E 'run_e1|e1_guard' | grep -v grep || echo NOTHING_RUNNING",
            timeout=30)

for lane, fraction in ((0, 0.92), (1, 0.45), (2, 0.45)):
    print(f"===== start cse lane {lane} (fraction {fraction}) =====")
    try:
        _remote.run(c, lane_cmd(lane, fraction) + f" echo CSE{lane}_LAUNCHED", timeout=15)
    except Exception as exc:
        print(f"lane {lane} launch (tolerated):", type(exc).__name__)
    time.sleep(3)

print("===== start guard v6 =====")
try:
    _remote.run(c, "nohup bash /root/mk_v2_runs/e1_guard.sh > /dev/null 2>&1 & echo GUARD_LAUNCHED", timeout=15)
except Exception as exc:
    print("guard launch (tolerated):", type(exc).__name__)

print("===== start 40-min mem sampler =====")
try:
    _remote.run(
        c,
        "rm -f /root/mk_v2_runs/e1_mem_samples.log; "
        "nohup bash -c 'for i in $(seq 240); do "
        "nvidia-smi --query-gpu=memory.used --format=csv,noheader >> /root/mk_v2_runs/e1_mem_samples.log; "
        "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader >> /root/mk_v2_runs/e1_mem_procs.log; "
        "sleep 10; done' > /dev/null 2>&1 & echo SAMPLER_STARTED",
        timeout=15,
    )
except Exception as exc:
    print("sampler (tolerated):", type(exc).__name__)

time.sleep(25)
print("===== verify =====")
_remote.run(c, "date '+%F %T %z'; ps -eo pid,args | awk '/run_e1_cse|e1_guard/ && !/awk/ {print $1, $(NF-1), $NF}'", timeout=30)
for lane in (0, 1, 2):
    _remote.run(c, f"tail -n 2 /root/mk_v2_runs/e1_cse_lane{lane}.log", timeout=30)
c.close()
print("CSE_LAUNCH_DONE")
