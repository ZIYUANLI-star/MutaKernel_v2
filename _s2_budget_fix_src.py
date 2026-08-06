#!/usr/bin/env python3
"""Fix stage-2 OOM churn: requeue SIGKILLed units, prep for 105GiB budget.

Root cause: guard restarted with BUDGET_GB=240 but the container cgroup
memory.max is 120 GiB; concurrent big units crossed it and got SIGKILL(-9).
This script (run while lanes are stopped and the pause marker is present):
  * finds stage-2 promoted units whose LATEST calibration row is run_error
    with exit_code -9,
  * moves them from done back to pending (queue surgery, with backup),
  * clears stale claims.
The guard is then relaunched by the caller with BUDGET_GB=105.
"""
import glob
import json
import shutil
from datetime import datetime
from pathlib import Path

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
QS = OUT / "queue_state.json"
TS = datetime.now().strftime("%Y%m%dT%H%M%S")

promoted = json.loads((OUT / "s2_promote_manifest.json").read_text(
    encoding="utf-8"))
promoted_units = set(promoted.get("promoted") or promoted.get("units") or [])
if not promoted_units:
    # fall back: units carrying the repair tag
    q0 = json.loads(QS.read_text(encoding="utf-8"))
    promoted_units = {k for k, u in q0["units"].items()
                      if "s2_schema_repair" in u}
print("stage-2 promoted units:", len(promoted_units))

# latest calibration row per unit (file order, last wins)
rows = {}
for f in sorted(glob.glob(str(OUT / "calibration_v2_lane*.jsonl"))):
    for line in open(f, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            rows[r["unit"]] = r

bad = sorted(u for u in promoted_units
             if u in rows and rows[u]["control_status"] == "run_error"
             and rows[u].get("exit_code") == -9)
print("SIGKILLed stage-2 units to requeue (%d):" % len(bad))
for u in bad:
    print(" ", u, "wall=", rows[u].get("wall_s"))

q = json.loads(QS.read_text(encoding="utf-8"))
shutil.copy2(QS, OUT / ("queue_state.json.bak_budgetfix_" + TS))

done = q["done"]
requeued = []
for u in bad:
    if isinstance(done, dict):
        done.pop(u, None)
    elif u in done:
        done.remove(u)
    if u not in q["pending"]:
        q["pending"].append(u)
        requeued.append(u)

stale = list(q["claimed"].keys())
for u in stale:
    if u not in q["pending"]:
        q["pending"].insert(0, u)
q["claimed"] = {}

q["s2_budget_fix"] = {
    "at": TS, "requeued": requeued, "released_claims": stale,
    "reason": "cgroup memory.max=120GiB; BUDGET_GB=240 admitted concurrent "
              "big units; cgroup OOM SIGKILL(-9); relaunch with BUDGET_GB=105",
}
tmp = QS.with_suffix(".tmp")
tmp.write_text(json.dumps(q, indent=1), encoding="utf-8")
tmp.replace(QS)
print("requeued:", len(requeued), "released claims:", stale)
print("pending now:", len(q["pending"]), "done now:", len(q["done"]))
print("S2_BUDGET_FIX_DONE")
