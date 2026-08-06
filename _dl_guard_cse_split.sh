#!/bin/bash
# E1 CSE guard v10.1 (two-lane): v9 + INCONCLUSIVE count in the progress line
# ("obs=N inconclusive=I") so watchdogs grepping progress lines see INC growth.
# Watches lane 3 (heavy-serial 0.92) + lane 4 (0.45). Lane 5 is CHAINED:
# it is only (re)started after CSE_DONE_LANE4 exists. AUTORESTART uses the
# correct 3600s budget (v7/v8 had a stale 1800s here).
RUNS=/root/mk_v2_runs
PIDFILE=$RUNS/e1_guard.pid

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "guard already running ($(cat "$PIDFILE"))"; exit 0
fi
echo $$ > "$PIDFILE"
for L in 3 4 5; do
  echo "[guard $(date '+%F %T %z')] GUARD_STARTED (v10.1 two-lane, chain lane5 after lane4, inconclusive counter) pid=$$" >> "$RUNS/e1_cse_lane$L.log"
done

launch_lane() {
  local L=$1 FRAC=$2
  echo "[guard $(date '+%F %T %z')] LAUNCH cse lane $L (frac=$FRAC, 3600s)" >> "$RUNS/e1_cse_lane$L.log"
  cd /root/mk_v2 && nohup env \
    PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin \
    TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext \
    MK_GPU_MEMORY_FRACTION=$FRAC \
    /root/miniconda3/bin/python -u scripts/run_e1_cse_falsify.py \
    --out-dir /root/mk_v2_runs/e1 --kernelbench-root KernelBench \
    --timeout 3600 --lane-plan /root/mk_v2_runs/e1/cse_lane_plan.json \
    --lane $L >> "$RUNS/e1_cse_lane$L.log" 2>&1 &
}

CYCLE=0
while true; do
  sleep 120
  CYCLE=$((CYCLE+1))
  for L in 3 4 5; do
    LOG=$RUNS/e1_cse_lane$L.log
    OBS=$RUNS/e1/cse_observations_lane$L.jsonl
    MARK=$RUNS/e1/CSE_DONE_LANE$L
    if [ -f "$MARK" ]; then continue; fi
    if [ $((CYCLE % 15)) -eq 0 ]; then
      N=$(wc -l < "$OBS" 2>/dev/null || echo 0)
      I=$(grep -c '"outcome": "INCONCLUSIVE"' "$OBS" 2>/dev/null); I=${I:-0}
      echo "[guard progress $(date '+%F %T %z')] cse lane $L obs=$N inconclusive=$I" >> "$LOG"
    fi
    if grep -q 'cse-falsify DONE' "$LOG"; then
      touch "$MARK"
      echo "[guard $(date '+%F %T %z')] cse lane $L DONE marker written" >> "$LOG"
      continue
    fi
    # lane 5 is chained: only run once lane 4 is done
    if [ "$L" = "5" ] && [ ! -f "$RUNS/e1/CSE_DONE_LANE4" ]; then continue; fi
    if ! pgrep -f "run_e1_cse_falsify.py.*--lane $L\$" > /dev/null; then
      if [ "$L" = "3" ]; then FRAC=0.92; else FRAC=0.45; fi
      echo "[guard $(date '+%F %T %z')] AUTORESTART cse lane $L" >> "$LOG"
      launch_lane $L $FRAC
    fi
  done
  if [ -f "$RUNS/e1/CSE_DONE_LANE3" ] && [ -f "$RUNS/e1/CSE_DONE_LANE4" ] && [ -f "$RUNS/e1/CSE_DONE_LANE5" ]; then
    touch "$RUNS/e1/CSE_DONE"
    echo "[guard $(date '+%F %T %z')] all lanes done; CSE_DONE written; guard exiting" >> "$RUNS/e1_cse_lane3.log"
    rm -f "$PIDFILE"
    exit 0
  fi
done
