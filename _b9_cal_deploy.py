# -*- coding: utf-8 -*-
"""Deploy B9 calibration skeleton: driver + prep + guard, compile-check,
then run prep (task table + manifest)."""
import io

import _remote as R

GUARD = """#!/bin/bash
# B9 calibration guard: restart dead lane drivers (max 20 restarts/lane),
# exit when every lane has its DONE marker.  Pattern-scoped to the B9 driver.
OUT=/root/mk_v2_runs/e3_b9_calib
PY=/root/miniconda3/bin/python
LANES=4
LOG=$OUT/guard_b9.log
echo "$(date '+%F %T') guard start pid=$$" >> "$LOG"
declare -A RESTARTS
while true; do
  alldone=1
  for L in $(seq 0 $((LANES-1))); do
    [ -f "$OUT/B9_CALIB_DONE_LANE$L" ] && continue
    alldone=0
    if ! pgrep -f "_b9_calib_driver.py --lane $L --lanes-total" > /dev/null; then
      n=${RESTARTS[$L]:-0}
      if [ "$n" -ge 20 ]; then
        echo "$(date '+%F %T') lane $L exceeded restart cap, HALT lane" >> "$LOG"
        continue
      fi
      RESTARTS[$L]=$((n+1))
      echo "$(date '+%F %T') lane $L not running -> start (restart #$((n+1)))" >> "$LOG"
      cd /root/mk_v2 && nohup env OMP_NUM_THREADS=24 MKL_NUM_THREADS=24 \
        "$PY" -u _b9_calib_driver.py --lane "$L" --lanes-total "$LANES" \
        >> "$OUT/lane$L.log" 2>&1 &
    fi
  done
  if [ "$alldone" -eq 1 ]; then
    echo "$(date '+%F %T') all lanes DONE, guard exit" >> "$LOG"
    break
  fi
  sleep 60
done
"""

c = R.connect()
R.run(c, "mkdir -p /root/mk_v2_runs/e3_b9_calib", timeout=30)
sftp = c.open_sftp()
for local, remote in [
    ("_b9_calib_driver.py", "/root/mk_v2/_b9_calib_driver.py"),
    ("_b9_calib_prep.py", "/root/mk_v2/_b9_calib_prep.py"),
]:
    with open(local, "r", encoding="utf-8") as fh:
        data = fh.read().replace("\r\n", "\n")
    sftp.putfo(io.BytesIO(data.encode("utf-8")), remote)
    print("put", local)
sftp.putfo(io.BytesIO(GUARD.replace("\r\n", "\n").encode("utf-8")),
           "/root/mk_v2_runs/e3_b9_calib/guard_b9.sh")
print("put guard_b9.sh")
sftp.close()

print("### compile check")
code, _, _ = R.run(c, "/root/miniconda3/bin/python -m py_compile "
                      "/root/mk_v2/_b9_calib_driver.py /root/mk_v2/_b9_calib_prep.py "
                      "&& bash -n /root/mk_v2_runs/e3_b9_calib/guard_b9.sh "
                      "&& echo COMPILE_OK", timeout=120)
if code != 0:
    raise SystemExit("ABORT: compile failed")

print("### prep (task table + manifest)")
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _b9_calib_prep.py",
      timeout=600)
c.close()
print("B9_DEPLOY_DONE")
