"""Restart the E1 equiv driver with --timeout 900 and deploy the guard loop."""
import io
import time

import _remote

DRIVER_CMD = (
    "cd /root/mk_v2 && nohup env "
    "PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
    "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
    "/root/miniconda3/bin/python -u scripts/run_e1_probe_study.py "
    "--phase equiv --kernelbench-root KernelBench "
    "--out-dir /root/mk_v2_runs/e1 --timeout 900 "
    ">> /root/mk_v2_runs/e1_equiv.log 2>&1 &"
)

GUARD_SH = """#!/bin/bash
# E1 equiv guard (2026-07-24 timeout fix): the 07-24 05:43 outage was a
# container stop/restart that killed the nohup'd driver mid-probe.  This loop
# relaunches the driver whenever it vanishes without a DONE marker.
LOG=/root/mk_v2_runs/e1_equiv.log
DONE_MARK=/root/mk_v2_runs/e1/EQUIV_DONE
PIDFILE=/root/mk_v2_runs/e1_guard.pid

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "guard already running ($(cat "$PIDFILE"))"; exit 0
fi
echo $$ > "$PIDFILE"
echo "[guard $(date '+%F %T %z')] GUARD_STARTED pid=$$" >> "$LOG"

while true; do
  sleep 120
  if [ -f "$DONE_MARK" ]; then
    echo "[guard $(date '+%F %T %z')] DONE marker present; guard exiting" >> "$LOG"
    exit 0
  fi
  if grep -q 'equiv DONE' "$LOG"; then
    touch "$DONE_MARK"
    echo "[guard $(date '+%F %T %z')] equiv DONE detected; guard exiting" >> "$LOG"
    exit 0
  fi
  if ! pgrep -f 'run_e1_probe_study.py --phase equiv' > /dev/null; then
    echo "[guard $(date '+%F %T %z')] AUTORESTART: driver missing, relaunching" >> "$LOG"
    cd /root/mk_v2 && nohup env \\
      PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin \\
      TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext \\
      /root/miniconda3/bin/python -u scripts/run_e1_probe_study.py \\
      --phase equiv --kernelbench-root KernelBench \\
      --out-dir /root/mk_v2_runs/e1 --timeout 900 >> "$LOG" 2>&1 &
  fi
done
"""

c = _remote.connect()

# Deploy guard script with LF endings via sftp file object.
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(GUARD_SH.replace("\r\n", "\n").encode()), "/root/mk_v2_runs/e1_guard.sh")
sftp.close()
_remote.run(c, "chmod +x /root/mk_v2_runs/e1_guard.sh", timeout=30)

print("===== start driver =====")
try:
    _remote.run(c, DRIVER_CMD + " echo DRIVER_LAUNCHED", timeout=20)
except Exception as exc:
    print("launch cmd returned/raised (tolerated):", type(exc).__name__, exc)

time.sleep(5)
print("===== start guard =====")
try:
    _remote.run(c, "nohup bash /root/mk_v2_runs/e1_guard.sh > /dev/null 2>&1 & echo GUARD_LAUNCHED", timeout=20)
except Exception as exc:
    print("guard launch (tolerated):", type(exc).__name__, exc)

time.sleep(10)
print("===== verify processes =====")
_remote.run(c, "ps aux | grep -E 'run_e1_probe_study|e1_guard' | grep -v grep || echo NOTHING_RUNNING", timeout=30)
print("===== log tail =====")
_remote.run(c, "tail -n 6 /root/mk_v2_runs/e1_equiv.log", timeout=30)
c.close()
print("RESTART_DONE")
