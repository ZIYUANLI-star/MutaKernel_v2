#!/bin/bash
# One-button B9 calibration resume (deployed to
# /root/mk_v2_runs/e3_b9_calib/resume_b9.sh).
#
#   bash resume_b9.sh                  # 2 lanes, 100 GiB budget, table order
#   bash resume_b9.sh --lanes 1        # strictly serial (safest)
#   bash resume_b9.sh --limit 4 --order desc   # pilot: 4 biggest units only
#   bash resume_b9.sh --dry-run        # print the plan + ETA, start nothing
#
# Sequence: precheck (critical path finished, fix deployed, GPU free) -> archive
# the pause marker -> archive the pre-fix records and build the queue -> start
# the guard.  Any failed precheck aborts before anything is written.
set -uo pipefail

OUT=/root/mk_v2_runs/e3_b9_calib
MK=/root/mk_v2
PY=/root/miniconda3/bin/python
LANES=2
BUDGET_GB=100
ORDER=table
LIMIT=0
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --lanes) LANES="$2"; shift 2 ;;
    --budget-gb) BUDGET_GB="$2"; shift 2 ;;
    --order) ORDER="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "unknown argument: $1"; exit 2 ;;
  esac
done
if [ "$LANES" != "1" ] && [ "$LANES" != "2" ]; then
  echo "refusing lanes=$LANES: the 120 GiB cap allows at most 2"; exit 2
fi

echo "### 1. precheck"
"$PY" "$MK/_b9_precheck.py" --budget-gb "$BUDGET_GB"
status=$?
if [ "$DRY_RUN" = "1" ]; then
  echo "### dry run: plan + ETA only"
  "$PY" "$MK/_b9_resume_prep.py" --order "$ORDER" --budget-gb "$BUDGET_GB" \
      ${LIMIT:+--limit "$LIMIT"}
  echo "DRY_RUN_DONE (precheck exit was $status)"
  exit 0
fi
if [ "$status" != "0" ]; then
  echo "ABORTED: precheck failed (GPU busy, critical path alive, or fix missing)"
  exit 1
fi

echo "### 2. archive the pause marker"
if [ -f "$OUT/PAUSED_FOR_SIGNOFF_RERUN" ]; then
  stamp=$(date '+%Y%m%dT%H%M%S')
  mkdir -p "$OUT/archive"
  mv "$OUT/PAUSED_FOR_SIGNOFF_RERUN" \
     "$OUT/archive/PAUSED_FOR_SIGNOFF_RERUN.lifted_$stamp"
  echo "lifted -> archive/PAUSED_FOR_SIGNOFF_RERUN.lifted_$stamp"
else
  echo "no pause marker in place"
fi

echo "### 3. archive pre-fix records + build the queue"
"$PY" "$MK/_b9_resume_prep.py" --commit --order "$ORDER" \
    --budget-gb "$BUDGET_GB" ${LIMIT:+--limit "$LIMIT"} || exit 1

echo "### 4. clear stale lane DONE markers"
rm -f "$OUT"/B9_CALIB_V2_DONE_LANE*

echo "### 5. start the guard ($LANES lane(s), ${BUDGET_GB} GiB budget)"
cd "$OUT" && LANES="$LANES" BUDGET_GB="$BUDGET_GB" \
  nohup bash "$OUT/guard_b9_v2.sh" > /dev/null 2>&1 &
echo "guard pid $!"
sleep 20

echo "### 6. state"
pgrep -af "_b9_calib_driver_v2.py --lane" | head
for L in $(seq 0 $((LANES-1))); do
  echo "--- lane $L ---"
  tail -3 "$OUT/lane_v2_$L.log" 2>/dev/null
done
tail -5 "$OUT/guard_b9_v2.log"
echo "RESUME_STARTED"
echo "pause again with: bash $OUT/pause_b9.sh"
