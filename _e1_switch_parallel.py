"""Switch the remote E1 equiv phase from serial to dual-lane parallel.

Order: kill guard first (so it cannot resurrect the serial driver), then the
driver, then any orphaned worker (start_new_session detaches its pgid).  The
probe-granularity checkpoint makes the interruption safe: the in-flight
probe simply reruns in its lane.
"""
import io
import time

import _remote

ENV = ("PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
       "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
       "MK_GPU_MEMORY_FRACTION=0.45")


def lane_cmd(lane):
    return (
        "cd /root/mk_v2 && nohup env " + ENV +
        " /root/miniconda3/bin/python -u scripts/run_e1_probe_study.py"
        " --phase equiv --kernelbench-root KernelBench"
        " --out-dir /root/mk_v2_runs/e1 --timeout 900"
        " --lane-plan /root/mk_v2_runs/e1/lane_plan.json"
        f" --lane {lane}"
        f" >> /root/mk_v2_runs/e1_equiv_lane{lane}.log 2>&1 &"
    )


GUARD_SH = """#!/bin/bash
# E1 equiv dual-lane guard (2026-07-24): relaunch either lane driver if it
# vanishes without its DONE marker; write EQUIV_DONE when both lanes finish.
RUNS=/root/mk_v2_runs
PIDFILE=$RUNS/e1_guard.pid

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "guard already running ($(cat "$PIDFILE"))"; exit 0
fi
echo $$ > "$PIDFILE"
for L in 0 1; do
  echo "[guard $(date '+%F %T %z')] GUARD_STARTED (dual-lane) pid=$$" >> "$RUNS/e1_equiv_lane$L.log"
done

while true; do
  sleep 120
  for L in 0 1; do
    LOG=$RUNS/e1_equiv_lane$L.log
    MARK=$RUNS/e1/EQUIV_DONE_LANE$L
    if [ -f "$MARK" ]; then continue; fi
    if grep -q 'equiv DONE' "$LOG"; then
      touch "$MARK"
      echo "[guard $(date '+%F %T %z')] lane $L DONE marker written" >> "$LOG"
      continue
    fi
    if ! pgrep -f "run_e1_probe_study.py.*--lane $L\\$" > /dev/null; then
      echo "[guard $(date '+%F %T %z')] AUTORESTART lane $L: driver missing, relaunching" >> "$LOG"
      cd /root/mk_v2 && nohup env \\
        PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin \\
        TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext \\
        MK_GPU_MEMORY_FRACTION=0.45 \\
        /root/miniconda3/bin/python -u scripts/run_e1_probe_study.py \\
        --phase equiv --kernelbench-root KernelBench \\
        --out-dir /root/mk_v2_runs/e1 --timeout 900 \\
        --lane-plan /root/mk_v2_runs/e1/lane_plan.json \\
        --lane $L >> "$LOG" 2>&1 &
    fi
  done
  if [ -f "$RUNS/e1/EQUIV_DONE_LANE0" ] && [ -f "$RUNS/e1/EQUIV_DONE_LANE1" ]; then
    touch "$RUNS/e1/EQUIV_DONE"
    echo "[guard $(date '+%F %T %z')] both lanes done; EQUIV_DONE written; guard exiting" >> "$RUNS/e1_equiv_lane0.log"
    rm -f "$PIDFILE"
    exit 0
  fi
done
"""

c = _remote.connect()

print("===== T0: stop guard, driver, workers =====")
_remote.run(c, "date '+%F %T %z'; "
               "kill $(cat /root/mk_v2_runs/e1_guard.pid 2>/dev/null) 2>/dev/null; "
               "pkill -f e1_guard.sh; sleep 1; "
               "pkill -f 'run_e1_probe_study.py --phase equiv'; sleep 1; "
               "pkill -f '_mutant_worker.py'; sleep 3; "
               "ps aux | grep -E 'run_e1|_mutant_worker|e1_guard' | grep -v grep || echo ALL_STOPPED",
            timeout=60)
print("===== GPU drain check =====")
_remote.run(c, "sleep 5; nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv", timeout=30)
print("===== global checkpoint snapshot at switch =====")
_remote.run(c, "wc -l /root/mk_v2_runs/e1/equiv_observations.jsonl; "
               "/root/miniconda3/bin/python -c \"import json; print('global completed:', len(json.load(open('/root/mk_v2_runs/e1/equiv_completed.json'))))\"",
            timeout=30)

sftp = c.open_sftp()
sftp.putfo(io.BytesIO(GUARD_SH.replace("\r\n", "\n").encode()), "/root/mk_v2_runs/e1_guard.sh")
sftp.close()
_remote.run(c, "chmod +x /root/mk_v2_runs/e1_guard.sh && rm -f /root/mk_v2_runs/e1_guard.pid", timeout=30)

for lane in (0, 1):
    print(f"===== start lane {lane} =====")
    try:
        _remote.run(c, lane_cmd(lane) + f" echo LANE{lane}_LAUNCHED", timeout=20)
    except Exception as exc:
        print(f"lane {lane} launch (tolerated):", type(exc).__name__, exc)
    time.sleep(3)

print("===== start guard =====")
try:
    _remote.run(c, "nohup bash /root/mk_v2_runs/e1_guard.sh > /dev/null 2>&1 & echo GUARD_LAUNCHED", timeout=20)
except Exception as exc:
    print("guard launch (tolerated):", type(exc).__name__, exc)

time.sleep(20)
print("===== verify processes =====")
_remote.run(c, "date '+%F %T %z'; ps aux | grep -E 'run_e1_probe_study|e1_guard' | grep -v grep | awk '{print $2, $11, $12, $13, $(NF-1), $NF}'", timeout=30)
print("===== lane log heads =====")
_remote.run(c, "tail -n 3 /root/mk_v2_runs/e1_equiv_lane0.log; echo ---; tail -n 3 /root/mk_v2_runs/e1_equiv_lane1.log", timeout=30)
c.close()
print("SWITCH_DONE")
