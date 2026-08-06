#!/bin/bash
# Final-window auto-trigger: launches the settlement orchestrator exactly once
# when lane3's DONE marker FILE exists.  Lesson from _cse_split_trigger.sh
# (which grepped logs and matched an empty file): this one tests marker-file
# existence directly with [ -f ], the same file the guard touches verbatim
# ($RUNS/e1/CSE_DONE_LANE$L).  All paths are env-overridable so a drill can
# run against a fake marker + --dry-run without touching the real chain.
MARK=${FW_MARK:-/root/mk_v2_runs/e1/CSE_DONE_LANE3}
LOG=${FW_LOG:-/root/mk_v2_runs/final_window_trigger.log}
LOCK=${FW_LOCK:-/root/mk_v2_runs/final_window_trigger.lock}
GO_ARGS=${FW_GO_ARGS:-}

if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date '+%F %T') another trigger instance holds $LOCK, exiting" >> "$LOG"
  exit 0
fi
echo "$(date '+%F %T') trigger started pid=$$ watching $MARK (go args: '$GO_ARGS')" >> "$LOG"
while true; do
  if [ -f "$MARK" ]; then
    echo "$(date '+%F %T') marker file present, launching orchestrator" >> "$LOG"
    cd /root/mk_v2 && /root/miniconda3/bin/python -u /root/mk_v2/_final_window_go.py $GO_ARGS >> "$LOG" 2>&1
    rc=$?
    echo "$(date '+%F %T') orchestrator exit=$rc" >> "$LOG"
    if [ $rc -eq 0 ]; then
      echo "$(date '+%F %T') FINAL_WINDOW_TRIGGERED_OK" >> "$LOG"
      break
    fi
    echo "$(date '+%F %T') orchestrator failed, retrying in 10min" >> "$LOG"
    sleep 600
  else
    sleep 60
  fi
done
rmdir "$LOCK"
