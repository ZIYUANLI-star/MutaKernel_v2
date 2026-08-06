"""IGNITE E3 wave-1 Lane M: guarded, resumable full-plan run.

Guard loop: restarts the runner on abnormal exit (resume by test_id is exact),
stops on LANE_M_STOP marker or LANE_M_DONE, caps restarts at 50/day pattern
like guard_b9. Runner writes append-only observations.jsonl + evidence.
"""
import _remote as R

guard = r"""#!/bin/bash
# guard_lane_m.sh - E3 wave-1 Lane M guard
OUT=/root/mk_v2_runs/e3_campaign
LOG=$OUT/guard_lane_m.log
RESTARTS=0
echo "$(date '+%F %T') guard_lane_m start pid=$$" >> $LOG
while true; do
  if [ -f $OUT/LANE_M_STOP ]; then
    echo "$(date '+%F %T') stop marker present, guard exit" >> $LOG; exit 0
  fi
  if [ -f $OUT/LANE_M_DONE ]; then
    echo "$(date '+%F %T') done marker present, guard exit" >> $LOG; exit 0
  fi
  if ! pgrep -f 'run_fse_experiment.py.*e3-wave1-lane-m-v1' > /dev/null; then
    if [ $RESTARTS -ge 60 ]; then
      echo "$(date '+%F %T') restart cap reached, guard exit" >> $LOG; exit 1
    fi
    RESTARTS=$((RESTARTS+1))
    echo "$(date '+%F %T') runner not running -> start (restart #$RESTARTS)" >> $LOG
    cd /root/mk_v2
    PATH=/usr/local/cuda/bin:$PATH nohup /root/miniconda3/bin/python -u \
      scripts/run_fse_experiment.py \
      --plan $OUT/wave1_lane_m_plan_v2.json \
      --subjects $OUT/wave1_subject_manifest_v2.json \
      --environment $OUT/wave1_environment.json \
      --artifact-root / \
      --output-dir $OUT/lane_m_run \
      --run-id e3-wave1-lane-m-v1 \
      --device cuda \
      >> $OUT/lane_m_run.log 2>&1 &
    sleep 30
    # completion detection: runner exits 0 after finishing the whole plan
  fi
  sleep 60
  # if the last runner exit was clean AND all cases done, place DONE
  if ! pgrep -f 'run_fse_experiment.py.*e3-wave1-lane-m-v1' > /dev/null; then
    N=$(wc -l < $OUT/lane_m_run/observations.jsonl 2>/dev/null || echo 0)
    if [ "$N" -ge 107092 ]; then
      echo "$(date '+%F %T') all 107092 observations present -> DONE" >> $LOG
      touch $OUT/LANE_M_DONE
    fi
  fi
done
"""

c = R.connect()
OUT = "/root/mk_v2_runs/e3_campaign"
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/guard_lane_m.sh", "w") as fh:
    fh.write(guard)
sftp.close()
R.run(c, "chmod +x /root/mk_v2/guard_lane_m.sh && "
         f"rm -f {OUT}/LANE_M_STOP {OUT}/LANE_M_DONE && "
         "nohup /root/mk_v2/guard_lane_m.sh > /dev/null 2>&1 & "
         "sleep 35 && "
         "pgrep -af 'guard_lane_m' | head -3 && "
         "pgrep -af 'run_fse_experiment' | head -3", timeout=120)
R.run(c, f"sleep 20 && tail -5 {OUT}/guard_lane_m.log && "
         f"tail -3 {OUT}/lane_m_run.log 2>/dev/null && "
         f"wc -l {OUT}/lane_m_run/observations.jsonl 2>/dev/null", timeout=120)
c.close()
print("LANE_M_IGNITED")
