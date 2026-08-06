#!/bin/bash
# Brake the B9 calibration run (deployed to
# /root/mk_v2_runs/e3_b9_calib/pause_b9.sh).
#
# Dropping the marker is the whole mechanism: each lane checks it between units,
# so lanes finish and record the unit in flight and then exit, and the guard
# refuses to restart them while it exists.  No process is signalled -- in
# particular no `pkill -f`, which would also match the ssh command line that
# invoked this script.  Progress is checkpointed per unit, so the only cost is
# the unit currently running.
OUT=/root/mk_v2_runs/e3_b9_calib

cat > "$OUT/PAUSED_FOR_SIGNOFF_RERUN" <<EOF
Paused $(date '+%F %T %z') by pause_b9.sh.
Lanes stop after the unit in flight; the guard will not restart them while this
file exists.  Resume with: bash $OUT/resume_b9.sh [--lanes 1|2]
EOF
echo "marker written:"
cat "$OUT/PAUSED_FOR_SIGNOFF_RERUN"

echo "--- lanes still finishing their in-flight unit ---"
pgrep -af "_b9_calib_driver_v2.py --lane" | head
echo "--- units in flight (from the queue state) ---"
/root/miniconda3/bin/python - "$OUT/queue_state.json" <<'EOF'
import json, sys
try:
    state = json.load(open(sys.argv[1]))
except OSError as exc:
    print("no queue state:", exc)
    raise SystemExit(0)
print("claimed:", json.dumps(state.get("claimed", {}), indent=2))
print("pending:", len(state.get("pending", [])), "done:", len(state.get("done", {})))
EOF
echo "PAUSE_MARKER_SET (poll until the lane logs show they stopped)"
