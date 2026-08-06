"""Remote-side standby: requeue resource-capped INCONCLUSIVE probes.

Dual-heavy concurrency (lanes 2/3, MK_GPU_MEMORY_FRACTION=0.45) can in the
worst case make an individual probe hit its own 36GB cap and land as
INCONCLUSIVE with an out-of-memory classification.  Run this AFTER all
lanes are done and BEFORE the merge:

  * scans every lane observation file for INCONCLUSIVE records whose
    inconclusive_class is 'out_of_memory' (or whose reason mentions the
    memory cap), moves those lines to equiv_observations_resource_v1.jsonl,
    and deletes the ids from that lane's completed file;
  * clears the affected lane's DONE marker and the global EQUIV_DONE so the
    relaunch (printed below, MK_GPU_MEMORY_FRACTION=0.9, single process,
    serial) reruns exactly the requeued probes with the full-GPU budget.

Idempotent per run; safe to run when there is nothing to requeue (no-op).
"""
import json
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
ARCHIVE = E1 / "equiv_observations_resource_v1.jsonl"
MARKERS = ("out of memory", "memory fraction", "cuda oom")

total = 0
affected = []
for lane in (0, 1, 2, 3):
    obs = E1 / f"equiv_observations_lane{lane}.jsonl"
    done = E1 / f"equiv_completed_lane{lane}.json"
    if not obs.exists():
        continue
    kept, voided, voided_ids = [], [], []
    for line in open(obs, encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        text = (json.dumps(row.get("reason", "")) + " "
                + str(row.get("inconclusive_class", ""))).lower()
        is_resource = (
            row.get("evidence_grade") == "INCONCLUSIVE"
            and (row.get("inconclusive_class") == "out_of_memory"
                 or any(m in text for m in MARKERS))
        )
        if is_resource:
            voided.append(line if line.endswith("\n") else line + "\n")
            voided_ids.append(row["probe_id"])
        else:
            kept.append(line if line.endswith("\n") else line + "\n")
    if not voided:
        continue
    with open(ARCHIVE, "a", encoding="utf-8") as fh:
        fh.writelines(voided)
    with open(obs, "w", encoding="utf-8") as fh:
        fh.writelines(kept)
    ids = set(json.load(open(done))) if done.exists() else set()
    done.write_text(json.dumps(sorted(ids - set(voided_ids))))
    (E1 / f"EQUIV_DONE_LANE{lane}").unlink(missing_ok=True)
    (E1 / "EQUIV_DONE").unlink(missing_ok=True)
    total += len(voided_ids)
    affected.append(lane)
    print(f"lane {lane}: requeued {len(voided_ids)} resource-capped probes: "
          f"{voided_ids}")

if not total:
    print("REQUEUE_RESOURCE_OK nothing to requeue")
else:
    print(f"REQUEUE_RESOURCE_OK total={total} lanes={affected}")
    print("relaunch each affected lane SERIALLY (one at a time, full budget):")
    for lane in affected:
        print(
            "cd /root/mk_v2 && nohup env "
            "PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
            "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
            "MK_GPU_MEMORY_FRACTION=0.9 "
            "/root/miniconda3/bin/python -u scripts/run_e1_probe_study.py "
            "--phase equiv --kernelbench-root KernelBench "
            "--out-dir /root/mk_v2_runs/e1 --timeout 900 "
            "--lane-plan /root/mk_v2_runs/e1/lane_plan.json "
            f"--lane {lane} >> /root/mk_v2_runs/e1_equiv_lane{lane}.log 2>&1 &")
