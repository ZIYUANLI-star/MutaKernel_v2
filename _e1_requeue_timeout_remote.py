"""Remote-side: move ALL timeout/resource INCONCLUSIVE records to archive and
prepare the serial requeue lane (plan lanes[4], tag 'requeue').

Filter (extended from the resource-only version): evidence_grade INCONCLUSIVE
and (timed_out true OR inconclusive_class in {timeout, out_of_memory}).
Completed LIKELY/WITNESSED records are never touched.

Actions:
  * per source file (global + lane0..3): back up (*.bak_requeue2), move
    matching lines to equiv_observations_timeout_v2.jsonl (v1 archive from
    the serial era is preserved untouched), delete the ids from the paired
    completed checkpoint;
  * append plan lanes[4] = kernels of archived + never-run probes;
  * assert: the requeue lane's pending set == archived ids + never-run ids.

Run only AFTER lanes 2/3 are stopped.  Refuses to run twice.
"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
ARCHIVE = E1 / "equiv_observations_timeout_v2.jsonl"

SOURCES = [
    ("global", E1 / "equiv_observations.jsonl", E1 / "equiv_completed.json"),
    ("lane0", E1 / "equiv_observations_lane0.jsonl", E1 / "equiv_completed_lane0.json"),
    ("lane1", E1 / "equiv_observations_lane1.jsonl", E1 / "equiv_completed_lane1.json"),
    ("lane2", E1 / "equiv_observations_lane2.jsonl", E1 / "equiv_completed_lane2.json"),
    ("lane3", E1 / "equiv_observations_lane3.jsonl", E1 / "equiv_completed_lane3.json"),
]

if ARCHIVE.exists():
    raise SystemExit("REFUSE: timeout_v2 archive exists; moveout already ran")


def requeueable(row):
    return (
        row.get("evidence_grade") == "INCONCLUSIVE"
        and (row.get("timed_out") is True
             or row.get("inconclusive_class") in ("timeout", "out_of_memory"))
    )


archived_ids = []
archived_lines = []
for name, obs, done in SOURCES:
    if not obs.exists():
        continue
    kept, moved, moved_ids = [], [], []
    for line in open(obs, encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        if requeueable(row):
            moved.append(line if line.endswith("\n") else line + "\n")
            moved_ids.append(row["probe_id"])
        else:
            kept.append(line if line.endswith("\n") else line + "\n")
    if not moved:
        print(f"{name}: 0 requeueable")
        continue
    shutil.copy2(obs, str(obs) + ".bak_requeue2")
    shutil.copy2(done, str(done) + ".bak_requeue2")
    with open(obs, "w", encoding="utf-8") as fh:
        fh.writelines(kept)
    ids = set(json.load(open(done)))
    assert set(moved_ids) <= ids, f"{name}: archived ids missing from completed"
    done.write_text(json.dumps(sorted(ids - set(moved_ids))))
    archived_ids.extend(moved_ids)
    archived_lines.extend(moved)
    print(f"{name}: moved {len(moved_ids)} (kept {len(kept)})")

with open(ARCHIVE, "w", encoding="utf-8") as fh:
    fh.writelines(archived_lines)

# --- never-run probes + requeue lane kernel set ---
survivors_by_kernel = {}
with open(E1 / "baseline_observations.jsonl", encoding="utf-8") as fh:
    for line in fh:
        row = json.loads(line)
        if row.get("status") == "survived":
            survivors_by_kernel.setdefault(row["kernel"], []).append(row["probe_id"])

completed_after = set(json.load(open(E1 / "equiv_completed.json")))
for lane_file in sorted(E1.glob("equiv_completed_lane*.json")):
    completed_after |= set(json.load(open(lane_file)))

pending_by_kernel = {
    k: [p for p in pids if p not in completed_after]
    for k, pids in survivors_by_kernel.items()
}
pending_by_kernel = {k: v for k, v in pending_by_kernel.items() if v}
pending_ids = {p for pids in pending_by_kernel.values() for p in pids}

archived_set = set(archived_ids)
never_run = pending_ids - archived_set
assert archived_set <= pending_ids, "archived ids must be pending after moveout"
print(f"archived={len(archived_set)} never_run={len(never_run)} "
      f"retry_total={len(pending_ids)}")
print("retry kernels:", {k: len(v) for k, v in sorted(pending_by_kernel.items())})

plan_path = E1 / "lane_plan.json"
plan = json.loads(plan_path.read_text(encoding="utf-8"))
if len(plan["lanes"]) == 4:
    plan["lanes"].append({
        "lane": 4,
        "tag": "requeue",
        "kernels": sorted(pending_by_kernel),
        "kernel_count": len(pending_by_kernel),
        "probe_count": len(pending_ids),
        "note": ("serial requeue of timeout/resource INCONCLUSIVEs "
                 "+ never-run remainder; MK_GPU_MEMORY_FRACTION=0.9, "
                 "--timeout 1800"),
    })
    plan["version"] = 3
    plan["v3_created_at"] = datetime.now(timezone.utc).isoformat()
    plan_path.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    print("plan v3 written (lanes[4])")
else:
    print(f"plan already has {len(plan['lanes'])} lanes; not appending")

# Final invariant: exactly the archived + never-run set is pending, and the
# grand account still adds up to 527.
assert pending_ids == archived_set | never_run
assert len(completed_after) + len(pending_ids) == 527, (
    f"account mismatch: {len(completed_after)} done + {len(pending_ids)} pending != 527")
print("MOVEOUT_V2_OK")
