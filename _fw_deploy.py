import _remote

TRIGGER = r"""#!/bin/bash
# E1 final-window auto-trigger v1 (2026-07-29).
# Fires /root/mk_v2/_final_window_go.py exactly once after lane3's DONE
# marker FILE exists.  Lesson from _cse_split_trigger.sh: do NOT grep logs
# for the marker name (empty-file markers / self-matching noise broke it);
# test the marker file itself with [ -f ].
MARK="${FW_MARK:-/root/mk_v2_runs/e1/CSE_DONE_LANE3}"
LOG="${FW_LOG:-/root/mk_v2_runs/final_window_trigger.log}"
LOCK="${FW_LOCK:-/root/mk_v2_runs/final_window_trigger.lock}"
GO_ARGS="${FW_GO_ARGS:-}"
DONE=/root/mk_v2_runs/e1/FINAL_WINDOW_DONE
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date '+%F %T %z') another trigger holds $LOCK, exiting" >> "$LOG"
  exit 0
fi
echo "$(date '+%F %T %z') trigger started pid=$$ watching=$MARK go_args='$GO_ARGS'" >> "$LOG"
while true; do
  if [ -n "$GO_ARGS" ] || [ ! -f "$DONE" ]; then :; else
    echo "$(date '+%F %T %z') FINAL_WINDOW_DONE already present, exiting" >> "$LOG"
    break
  fi
  if [ -f "$MARK" ]; then
    echo "$(date '+%F %T %z') marker file present, launching orchestrator" >> "$LOG"
    cd /root/mk_v2 && /root/miniconda3/bin/python -u /root/mk_v2/_final_window_go.py $GO_ARGS >> "$LOG" 2>&1
    rc=$?
    echo "$(date '+%F %T %z') orchestrator exit=$rc" >> "$LOG"
    if [ $rc -eq 0 ]; then
      echo "$(date '+%F %T %z') FINAL_WINDOW_TRIGGERED_OK" >> "$LOG"
      break
    fi
    echo "$(date '+%F %T %z') orchestrator failed (rc=$rc), retry in 600s" >> "$LOG"
    sleep 600
  else
    sleep 60
  fi
done
rmdir "$LOCK"
"""

c = _remote.connect()
s = c.open_sftp()
s.put("_fw_go_source.py", "/root/mk_v2/_final_window_go.py")
with s.open("/root/mk_v2/_final_window_trigger.sh", "w") as f:
    f.write(TRIGGER)
s.close()

for cmd in [
    "chmod +x /root/mk_v2/_final_window_trigger.sh && bash -n /root/mk_v2/_final_window_trigger.sh && echo BASH_SYNTAX_OK",
    "/root/miniconda3/bin/python -m py_compile /root/mk_v2/_final_window_go.py && echo PY_COMPILE_OK",
    # char-by-char marker path check: what guard writes vs what trigger watches
    "GUARD_MARK=$(bash -c 'RUNS=/root/mk_v2_runs; L=3; echo \"$RUNS/e1/CSE_DONE_LANE$L\"'); "
    "TRIG_MARK=$(bash -c 'source /dev/stdin <<<\"$(grep ^MARK= /root/mk_v2/_final_window_trigger.sh)\"; echo \"$MARK\"'); "
    "echo \"guard_writes=[$GUARD_MARK]\"; echo \"trigger_watches=[$TRIG_MARK]\"; "
    "[ \"$GUARD_MARK\" = \"$TRIG_MARK\" ] && echo MARKER_PATH_MATCH || echo MARKER_PATH_MISMATCH",
    # cross-check against the real lane4/5 markers the guard actually wrote
    "ls -la /root/mk_v2_runs/e1/CSE_DONE_LANE4 /root/mk_v2_runs/e1/CSE_DONE_LANE5",
    "grep -n 'MARK=\\$RUNS/e1/CSE_DONE_LANE\\$L' /root/mk_v2_runs/e1_guard_cse_split.sh",
]:
    print("### " + cmd[:80])
    _remote.run(c, cmd, timeout=60)
c.close()
print("DEPLOY_DONE")
