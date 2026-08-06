#!/bin/bash
# B9 calibration guard v2 (deployed to /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.sh).
#
# Restarts dead lane drivers (cap 20 per lane) and exits once every lane has its
# DONE marker.  Two brakes it must never fight:
#   * PAUSED_FOR_SIGNOFF_RERUN -> do not start anything, keep watching so that
#     removing the marker resumes the run;
#   * a live critical-path _mutant_worker.py -> do not start anything.
# Both checks are read-only /proc scans (never `pkill -f`, which matches the
# invoking shell's own command line).
OUT=/root/mk_v2_runs/e3_b9_calib
PY=/root/miniconda3/bin/python
LOG=$OUT/guard_b9_v2.log
LANES=${LANES:-2}
BUDGET_GB=${BUDGET_GB:-100}

echo "$(date '+%F %T') guard v2 start pid=$$ lanes=$LANES budget=${BUDGET_GB}GiB" >> "$LOG"
declare -A RESTARTS
while true; do
  if [ -f "$OUT/PAUSED_FOR_SIGNOFF_RERUN" ]; then
    echo "$(date '+%F %T') paused marker present, not starting lanes" >> "$LOG"
    sleep 60
    continue
  fi
  if "$PY" -c "
import os, sys
from pathlib import Path
def ppid(pid):
    try:
        for line in open('/proc/%d/status' % pid):
            if line.startswith('PPid:'):
                return int(line.split()[1])
    except OSError:
        pass
    return 0
excluded, pid = set(), os.getpid()
while pid and pid != 1:
    excluded.add(pid); pid = ppid(pid)
for entry in os.listdir('/proc'):
    if not entry.isdigit() or int(entry) in excluded:
        continue
    try:
        raw = Path('/proc/%s/cmdline' % entry).read_bytes()
    except OSError:
        continue
    if '_mutant_worker.py' in raw.replace(b'\0', b' ').decode('utf-8', 'replace'):
        sys.exit(0)
sys.exit(1)
"; then
    echo "$(date '+%F %T') critical-path worker alive, not starting lanes" >> "$LOG"
    sleep 60
    continue
  fi

  alldone=1
  for L in $(seq 0 $((LANES-1))); do
    [ -f "$OUT/B9_CALIB_V2_DONE_LANE$L" ] && continue
    alldone=0
    if ! pgrep -f "_b9_calib_driver_v2.py --lane $L " > /dev/null; then
      n=${RESTARTS[$L]:-0}
      if [ "$n" -ge 20 ]; then
        echo "$(date '+%F %T') lane $L exceeded restart cap, HALT lane" >> "$LOG"
        continue
      fi
      RESTARTS[$L]=$((n+1))
      echo "$(date '+%F %T') lane $L not running -> start (restart #$((n+1)))" >> "$LOG"
      cd /root/mk_v2 && nohup env OMP_NUM_THREADS=24 MKL_NUM_THREADS=24 \
        "$PY" -u _b9_calib_driver_v2.py --lane "$L" \
        --budget-gb "$BUDGET_GB" \
        >> "$OUT/lane_v2_$L.log" 2>&1 &
    fi
  done
  if [ "$alldone" -eq 1 ]; then
    echo "$(date '+%F %T') all lanes DONE, guard exit" >> "$LOG"
    break
  fi
  sleep 60
done
