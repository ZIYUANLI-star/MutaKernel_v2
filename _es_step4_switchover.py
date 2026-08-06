"""Step 4: full switchover to early-stop-on-fail for Lane M.

Order: stop guard+runner -> rewrite guard -> archive run manifest v1 ->
git commit -> recapture environment -> relaunch -> verify.
"""
import time
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
      --environment $OUT/wave1_environment.json \\
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

print("### 1. stop guard + runner")
R.run(c, "touch /root/mk_v2_runs/e3_campaign/LANE_M_STOP", timeout=30)
R.run(c, "pkill -f 'run_fse_[e]xperiment.py.*e3-wave1-lane-m-v1'; "
         "pkill -f '_candidate_[w]orker.py'; sleep 2; "
         "pgrep -af 'run_fse_[e]xperiment|_candidate_[w]orker|guard_[l]ane_m' || echo ALL_STOPPED",
      timeout=60)
# guard may take up to 60s to see the stop marker
time.sleep(65)
R.run(c, "pgrep -af 'guard_[l]ane_m' || echo GUARD_STOPPED", timeout=30)

print("### 2. rewrite guard script")
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/guard_lane_m.sh", "w") as fh:
    fh.write(GUARD)
sftp.close()
R.run(c, "chmod +x /root/mk_v2/guard_lane_m.sh && bash -n /root/mk_v2/guard_lane_m.sh "
         "&& echo GUARD_SYNTAX_OK", timeout=30)

print("### 3. archive run manifest v1")
R.run(c, "cd /root/mk_v2_runs/e3_campaign/lane_m_run && "
         "cp -a run_manifest.json run_manifest_v1_pre_earlystop.json && "
         "rm run_manifest.json && ls -la run_manifest* 2>/dev/null; "
         "ls run_manifest_v1_pre_earlystop.json && echo MANIFEST_ARCHIVED",
      timeout=30)

print("### 4. git commit")
R.run(c, "cd /root/mk_v2 && git add guard_lane_m.sh && "
         "git commit -m 'lane-m guard v2: enable preregistered early-stop-on-fail; "
         "summary-based DONE detection' && git log --oneline -1", timeout=60)

print("### 5. recapture environment")
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python scripts/capture_fse_environment.py "
         "--output /root/mk_v2_runs/e3_campaign/wave1_environment.json && "
         "/root/miniconda3/bin/python -c \"import json;"
         "d=json.load(open('/root/mk_v2_runs/e3_campaign/wave1_environment.json'));"
         "print('git:',d.get('git'))\"", timeout=300)

print("### 6. relaunch guard")
R.run(c, "rm -f /root/mk_v2_runs/e3_campaign/LANE_M_STOP && "
         "cd /root/mk_v2 && nohup ./guard_lane_m.sh > /dev/null 2>&1 & "
         "sleep 40; pgrep -af 'guard_[l]ane_m'; pgrep -af 'run_fse_[e]xperiment' "
         "| head -2", timeout=120)

print("### 7. verify no refusal + manifest v2 created")
R.run(c, "sleep 20; tail -n 3 /root/mk_v2_runs/e3_campaign/lane_m_run.log; "
         "ls -la /root/mk_v2_runs/e3_campaign/lane_m_run/run_manifest.json && "
         "tail -n 2 /root/mk_v2_runs/e3_campaign/guard_lane_m.log", timeout=120)
c.close()
print("SWITCHOVER_DONE")
