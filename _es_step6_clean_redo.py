"""Step 6: clean redo - guard v2 w/ env_v2, inline-identity commit, capture,
integrity check, relaunch."""
import _remote as R

GUARD = """#!/bin/bash
# guard_lane_m.sh - E3 wave-1 Lane M guard (v2: early-stop-on-fail enabled)
OUT=/root/mk_v2_runs/e3_campaign
LOG=$OUT/guard_lane_m.log
RESTARTS=0
echo "$(date '+%F %T') guard_lane_m v2 start pid=$$" >> $LOG
while true; do
  if [ -f $OUT/LANE_M_STOP ]; then
    echo "$(date '+%F %T') stop marker present, guard exit" >> $LOG; exit 0
  fi
  if [ -f $OUT/LANE_M_DONE ]; then
    echo "$(date '+%F %T') done marker present, guard exit" >> $LOG; exit 0
  fi
  if ! pgrep -f 'run_fse_experiment.py.*e3-wave1-lane-m-v1' > /dev/null; then
    LAST=$(tail -n 1 $OUT/lane_m_run.log 2>/dev/null)
    case "$LAST" in
      *'"skipped_after_fail"'*)
        echo "$(date '+%F %T') runner finished plan: $LAST -> DONE" >> $LOG
        touch $OUT/LANE_M_DONE
        continue ;;
    esac
    if [ $RESTARTS -ge 60 ]; then
      echo "$(date '+%F %T') restart cap reached, guard exit" >> $LOG; exit 1
    fi
    RESTARTS=$((RESTARTS+1))
    echo "$(date '+%F %T') runner not running -> start (restart #$RESTARTS)" >> $LOG
    cd /root/mk_v2
    PATH=/usr/local/cuda/bin:$PATH nohup /root/miniconda3/bin/python -u \\
      scripts/run_fse_experiment.py \\
      --plan $OUT/wave1_lane_m_plan_v2.json \\
      --subjects $OUT/wave1_subject_manifest_v2.json \\
      --environment $OUT/wave1_environment_v2.json \\
      --artifact-root / \\
      --output-dir $OUT/lane_m_run \\
      --run-id e3-wave1-lane-m-v1 \\
      --device cuda \\
      --early-stop-on-fail \\
      >> $OUT/lane_m_run.log 2>&1 &
    sleep 30
  fi
  sleep 60
done
"""

c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/guard_lane_m.sh", "w") as fh:
    fh.write(GUARD)
sftp.close()

print("### commit guard v2")
R.run(c, "cd /root/mk_v2 && chmod +x guard_lane_m.sh && bash -n guard_lane_m.sh && "
         "git add guard_lane_m.sh && "
         "git -c user.name='mk-ops' -c user.email='ops@mk.local' commit -m "
         "'lane-m guard v2: enable preregistered early-stop-on-fail; env manifest v2; "
         "summary-based DONE detection' && git log --oneline -1 && "
         "git status --porcelain | head -3; echo COMMIT_STEP_END", timeout=120)

print("### capture environment v2")
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python scripts/capture_fse_environment.py "
         "--output /root/mk_v2_runs/e3_campaign/wave1_environment_v2.json && "
         "/root/miniconda3/bin/python -c \"import json;"
         "d=json.load(open('/root/mk_v2_runs/e3_campaign/wave1_environment_v2.json'));"
         "print('git:', d.get('git'))\"", timeout=300)

print("### ledger integrity: did the brief dirty runner write anything?")
R.run(c, "wc -l /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl; "
         "ls -la /root/mk_v2_runs/e3_campaign/lane_m_run/run_manifest*.json 2>/dev/null; "
         "tail -n 2 /root/mk_v2_runs/e3_campaign/lane_m_run.log", timeout=60)
c.close()
print("REDO_DONE")
