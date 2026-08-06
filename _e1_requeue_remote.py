"""Remote-side requeue of the 64 voided timeout-INCONCLUSIVE equiv probes.

Runs on the A800 under /root/miniconda3/bin/python.  Idempotent: refuses to
run twice (backup files must not already exist).
"""
import json
import shutil
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
OBS = E1 / "equiv_observations.jsonl"
DONE = E1 / "equiv_completed.json"
OBS_BAK = E1 / "equiv_observations.jsonl.bak_timeoutfix"
DONE_BAK = E1 / "equiv_completed.json.bak_timeoutfix"
ARCHIVE = E1 / "equiv_observations_timeout_v1.jsonl"

if OBS_BAK.exists() or DONE_BAK.exists():
    raise SystemExit("REFUSE: backup files already exist; requeue ran before")

shutil.copy2(OBS, OBS_BAK)
shutil.copy2(DONE, DONE_BAK)

kept_lines, voided_lines, voided_ids = [], [], []
with open(OBS, encoding="utf-8") as fh:
    for line in fh:
        if not line.strip():
            continue
        row = json.loads(line)
        is_voided = (
            row.get("evidence_grade") == "INCONCLUSIVE"
            and row.get("timed_out") is True
            and row.get("inconclusive_class") == "timeout"
        )
        if is_voided:
            voided_lines.append(line if line.endswith("\n") else line + "\n")
            voided_ids.append(row["probe_id"])
        else:
            kept_lines.append(line if line.endswith("\n") else line + "\n")

assert len(voided_ids) == 64, f"expected 64 voided records, got {len(voided_ids)}"
assert len(kept_lines) == 68, f"expected 68 kept records, got {len(kept_lines)}"

with open(ARCHIVE, "w", encoding="utf-8") as fh:
    fh.writelines(voided_lines)
with open(OBS, "w", encoding="utf-8") as fh:
    fh.writelines(kept_lines)

completed = json.loads(DONE.read_text())
assert len(completed) == 132, f"expected 132 completed ids, got {len(completed)}"
new_completed = sorted(set(completed) - set(voided_ids))
assert len(new_completed) == 68, f"expected 68 remaining ids, got {len(new_completed)}"
DONE.write_text(json.dumps(new_completed))

# Cross-check: kept observation ids == remaining completed ids, 1:1.
kept_ids = sorted(json.loads(l)["probe_id"] for l in kept_lines)
assert kept_ids == new_completed, "kept obs ids != remaining completed ids"

kernels = sorted({pid.split("__", 1)[0] for pid in voided_ids})
print("REQUEUE_OK kept=68 voided=64")
print("voided kernels:", ",".join(kernels))
print("archive:", ARCHIVE)
