#!/usr/bin/env python3
"""Repair the 44 promoted stage-2 unit records in queue_state.json.

The s2 promotion copied the thin stage2_deferred summaries (unit, sizing
estimates only) into q['units']; the driver needs the full stage-1 schema
(task_key, dtype, task_file, reduction_heavy, in_numel, ...).  Rebuild the
missing fields from task_table.json + unit_size_table.json, keep the sizing
and timeout values already computed at promotion time, release the two
stale claimed entries back to pending, then lift the pause marker.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
QS = OUT / "queue_state.json"
TS = datetime.now().strftime("%Y%m%dT%H%M%S")

q = json.loads(QS.read_text(encoding="utf-8"))
table = json.loads((OUT / "task_table.json").read_text(encoding="utf-8"))
sizes = json.loads((OUT / "unit_size_table.json").read_text(encoding="utf-8"))
by_key_task = {t["task_key"]: t for t in table["tasks"]}
by_key_size = {s["task_key"]: s for s in sizes["subjects"]}

targets = list(q["pending"]) + list(q["claimed"].keys())
fixed, already_ok = [], []
for uid in targets:
    u = q["units"][uid]
    if "task_key" in u and "task_file" in u:
        already_ok.append(uid)
        continue
    task_key, dtype = uid.rsplit("__", 1)
    task = by_key_task.get(task_key)
    size = by_key_size.get(task_key, {})
    if task is None:
        raise SystemExit("no task_table entry for %s" % task_key)
    if dtype not in task["dtypes"]:
        raise SystemExit("dtype %s not in task table for %s" % (dtype, task_key))
    u["task_key"] = task_key
    u["dtype"] = dtype
    u["task_file"] = task["file"]
    u["reduction_heavy"] = task["reduction_heavy"]
    u["in_numel"] = size.get("in_numel") or 0
    if "out_numel" not in u:
        u["out_numel"] = size.get("out_numel") or 0
    u["above_quantile_limit"] = u["out_numel"] > 2 ** 24
    u["previous_status"] = None
    u["s2_schema_repair"] = TS
    fixed.append(uid)

# release stale claims (their pids are long dead)
released = list(q["claimed"].keys())
for uid in released:
    if uid not in q["pending"]:
        q["pending"].insert(0, uid)
q["claimed"] = {}

shutil.copy2(QS, OUT / ("queue_state.json.bak_s2repair_" + TS))
tmp = QS.with_suffix(".tmp")
tmp.write_text(json.dumps(q, indent=1), encoding="utf-8")
tmp.replace(QS)

print("fixed:", len(fixed), "already_ok:", len(already_ok),
      "released_claims:", released)
print("pending now:", len(q["pending"]))

# sanity: driver-required fields present on every pending unit
need = ["unit", "task_key", "dtype", "task_file", "reduction_heavy",
        "out_numel", "in_numel", "est_peak_gb", "reserve_gb",
        "est_wall_s_fast", "est_wall_s_slow", "unit_timeout_s"]
bad = [uid for uid in q["pending"]
       if any(k not in q["units"][uid] for k in need)]
if bad:
    raise SystemExit("STILL BROKEN: %r" % bad[:5])
print("schema check OK on all pending units")

# lift the pause marker so the guard resumes
marker = OUT / "PAUSED_FOR_SIGNOFF_RERUN"
if marker.exists():
    marker.unlink()
    print("pause marker lifted")
print("S2_REPAIR_DONE")
