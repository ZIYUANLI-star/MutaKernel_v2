"""Second split: stop lane0, start lanes 2/3 (dual-heavy concurrency).

Kill discipline: guard first (pidfile), then lane0 driver by exact PID
(parsed from ps on the Python side), then its worker by PPID.  No pkill
pattern matching (last switch's self-match lesson).
"""
import io
import re
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
# E1 equiv guard v3 (2026-07-24 23h): watch lanes 2 and 3 (re-split of
# lane0's remainder; lanes 0/1 are retired/complete).
RUNS=/root/mk_v2_runs
PIDFILE=$RUNS/e1_guard.pid

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "guard already running ($(cat "$PIDFILE"))"; exit 0
fi
echo $$ > "$PIDFILE"
for L in 2 3; do
  echo "[guard $(date '+%F %T %z')] GUARD_STARTED (lanes 2/3) pid=$$" >> "$RUNS/e1_equiv_lane$L.log"
done

while true; do
  sleep 120
  for L in 2 3; do
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
  if [ -f "$RUNS/e1/EQUIV_DONE_LANE2" ] && [ -f "$RUNS/e1/EQUIV_DONE_LANE3" ]; then
    touch "$RUNS/e1/EQUIV_DONE"
    echo "[guard $(date '+%F %T %z')] lanes 2+3 done; EQUIV_DONE written; guard exiting" >> "$RUNS/e1_equiv_lane2.log"
    rm -f "$PIDFILE"
    exit 0
  fi
done
"""

c = _remote.connect()

print("===== T0 =====")
_remote.run(c, "date '+%F %T %z'", timeout=20)

print("===== stop guard (pidfile) =====")
_remote.run(c, "GP=$(cat /root/mk_v2_runs/e1_guard.pid 2>/dev/null); "
               "echo guard_pid: $GP; kill $GP 2>/dev/null; "
               "rm -f /root/mk_v2_runs/e1_guard.pid; sleep 1; "
               "ps -p $GP > /dev/null 2>&1 && echo GUARD_STILL_ALIVE || echo GUARD_STOPPED",
            timeout=30)

print("===== locate lane0 driver + worker =====")
_, out, _ = _remote.run(c, "ps -eo pid,ppid,args", timeout=30, echo=False)
driver_pid = None
for line in out.splitlines():
    if "run_e1_probe_study.py" in line and "--lane 0" in line and "python" in line:
        driver_pid = int(line.split()[0])
        print("lane0 driver:", line.strip()[:120])
if driver_pid is None:
    raise SystemExit("ABORT: lane0 driver not found")
worker_pids = [int(l.split()[0]) for l in out.splitlines()
               if "_mutant_worker.py" in l and re.match(rf"^\s*\d+\s+{driver_pid}\s", l)]
print("lane0 worker pids:", worker_pids)

print("===== kill lane0 by PID =====")
pids = " ".join(str(p) for p in [driver_pid] + worker_pids)
_remote.run(c, f"kill -9 {pids} 2>/dev/null; sleep 2; "
               "ps -eo pid,args | grep -E 'run_e1|_mutant_worker' | grep -v grep || echo LANE0_STOPPED",
            timeout=30)

print("===== account check =====")
_remote.run(
    c,
    "/root/miniconda3/bin/python -c \""
    "import json; g=set(json.load(open('/root/mk_v2_runs/e1/equiv_completed.json')));"
    "l0=set(json.load(open('/root/mk_v2_runs/e1/equiv_completed_lane0.json')));"
    "l1=set(json.load(open('/root/mk_v2_runs/e1/equiv_completed_lane1.json')));"
    "u=g|l0|l1; print('global',len(g),'lane0',len(l0),'lane1',len(l1),'union',len(u),"
    "'overlap_ok',len(u)==len(g)+len(l0)+len(l1),'remaining',527-len(u))\"",
    timeout=30,
)

sftp = c.open_sftp()
sftp.putfo(io.BytesIO(GUARD_SH.replace("\r\n", "\n").encode()),
           "/root/mk_v2_runs/e1_guard.sh")
sftp.close()
_remote.run(c, "chmod +x /root/mk_v2_runs/e1_guard.sh", timeout=20)

for lane in (2, 3):
    print(f"===== start lane {lane} =====")
    try:
        _remote.run(c, lane_cmd(lane) + f" echo LANE{lane}_LAUNCHED", timeout=15)
    except Exception as exc:
        print(f"lane {lane} launch (tolerated):", type(exc).__name__)
    time.sleep(3)

print("===== start guard v3 =====")
try:
    _remote.run(c, "nohup bash /root/mk_v2_runs/e1_guard.sh > /dev/null 2>&1 & echo GUARD_LAUNCHED", timeout=15)
except Exception as exc:
    print("guard launch (tolerated):", type(exc).__name__)

time.sleep(20)
print("===== verify =====")
_remote.run(c, "date '+%F %T %z'; ps -eo pid,args | awk '/run_e1_probe_study|e1_guard/ && !/awk/ {print $1, $(NF-1), $NF}'", timeout=30)
_remote.run(c, "tail -n 2 /root/mk_v2_runs/e1_equiv_lane2.log; echo ---; tail -n 2 /root/mk_v2_runs/e1_equiv_lane3.log", timeout=30)
c.close()
print("SWITCH_V2_DONE")
