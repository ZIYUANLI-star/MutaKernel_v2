import _remote

TRIGGER = r"""#!/bin/bash
# Auto-trigger for the CSE lane0 split: waits until both light lanes are done,
# then runs the (self-validating) switch script exactly once.
LOG=/root/mk_v2_runs/cse_split_trigger.log
LOCK=/root/mk_v2_runs/cse_split_trigger.lock
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date '+%F %T') another trigger instance holds the lock, exiting" >> "$LOG"
  exit 0
fi
echo "$(date '+%F %T') trigger started (pid $$)" >> "$LOG"
while true; do
  d1=$(grep -c CSE_DONE_LANE1 /root/mk_v2_runs/e1_cse_lane1.log 2>/dev/null)
  d2=$(grep -c CSE_DONE_LANE2 /root/mk_v2_runs/e1_cse_lane2.log 2>/dev/null)
  if [ "${d1:-0}" -gt 0 ] && [ "${d2:-0}" -gt 0 ]; then
    echo "$(date '+%F %T') both light lanes done, executing split" >> "$LOG"
    /root/miniconda3/bin/python /root/mk_v2/_cse_split_go.py >> "$LOG" 2>&1
    rc=$?
    echo "$(date '+%F %T') split script exit=$rc" >> "$LOG"
    if [ $rc -eq 0 ]; then
      echo "$(date '+%F %T') SPLIT_TRIGGERED_OK" >> "$LOG"
      break
    fi
    echo "$(date '+%F %T') split failed, will retry in 10min" >> "$LOG"
  fi
  sleep 600
done
rmdir "$LOCK"
"""

c = _remote.connect()
s = c.open_sftp()
with s.open("/root/mk_v2/_cse_split_trigger.sh", "w") as f:
    f.write(TRIGGER)
s.close()
_, out, _ = _remote.run(
    c,
    "chmod +x /root/mk_v2/_cse_split_trigger.sh && "
    "nohup /root/mk_v2/_cse_split_trigger.sh >/dev/null 2>&1 & sleep 2; "
    "ps aux | grep '_cse_split_[t]rigger' | grep -v grep; "
    "tail -3 /root/mk_v2_runs/cse_split_trigger.log",
    timeout=60, echo=False)
c.close()
print(out)
print("DEPLOY_DONE")
