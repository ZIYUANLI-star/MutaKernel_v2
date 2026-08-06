"""Remote-side: merge lane observations back into the global equiv files.

v3 (timeout requeue): merges SIX sources — the pre-switch global file,
lanes 0/1 (first split), lanes 2/3 (re-split of lane0's remainder), and the
serial requeue lane (lane4_requeue).  Run only after all live lanes are
done (EQUIV_DONE marker).  Idempotent: refuses to run twice (premerge
backups must not exist).  Asserts: merged ids are unique (each id exactly
once), equal to the baseline-survivor set, and total 527.  Prints the final
grade distribution.
"""
import json
import shutil
from collections import Counter
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
OBS = E1 / "equiv_observations.jsonl"
DONE = E1 / "equiv_completed.json"


def read_lines(path):
    if not path.exists():
        return []
    return [l for l in open(path, encoding="utf-8") if l.strip()]


if (E1 / "equiv_observations.jsonl.bak_premerge").exists():
    raise SystemExit("REFUSE: premerge backup exists; merge already ran")
if not (E1 / "EQUIV_DONE").exists():
    raise SystemExit("REFUSE: EQUIV_DONE marker missing; lanes not finished")

base = read_lines(OBS)
lane_names = ["lane0", "lane1", "lane2", "lane3", "lane4_requeue"]
lanes = {
    name: read_lines(E1 / f"equiv_observations_{name}.jsonl")
    for name in lane_names
}
all_lines = base + [l for name in lane_names for l in lanes[name]]
rows = [json.loads(l) for l in all_lines]
ids = [r["probe_id"] for r in rows]

survivors = set()
with open(E1 / "baseline_observations.jsonl", encoding="utf-8") as fh:
    for line in fh:
        row = json.loads(line)
        if row.get("status") == "survived":
            survivors.add(row["probe_id"])

counts = Counter(ids)
dupes = [pid for pid, n in counts.items() if n > 1]
assert not dupes, f"duplicate probe ids after merge: {dupes[:5]}"
assert all(n == 1 for n in counts.values()), "every id must appear exactly once"
missing = sorted(survivors - set(ids))
extra = sorted(set(ids) - survivors)
assert not missing and not extra, f"missing={missing[:5]} extra={extra[:5]}"
assert len(ids) == 527, f"expected 527 merged records, got {len(ids)}"

shutil.copy2(OBS, E1 / "equiv_observations.jsonl.bak_premerge")
shutil.copy2(DONE, E1 / "equiv_completed.json.bak_premerge")
with open(OBS, "w", encoding="utf-8") as fh:
    fh.writelines(l if l.endswith("\n") else l + "\n" for l in all_lines)
DONE.write_text(json.dumps(sorted(ids)))

grades = Counter(r["evidence_grade"] for r in rows)
budget_exhausted = sum(
    1 for r in rows if (r.get("evidence") or {}).get("budget_exhausted"))
inconclusive_classes = Counter(
    r.get("inconclusive_class") for r in rows
    if r["evidence_grade"] == "INCONCLUSIVE")
(E1 / "equiv_summary.json").write_text(json.dumps({
    "merged_from": ["global(serial)"] + lane_names,
    "completed": len(ids),
    "grades": dict(grades),
    "likely_with_budget_exhausted": budget_exhausted,
    "inconclusive_classes": dict(inconclusive_classes),
}, indent=2), encoding="utf-8")
lane_counts = {name: len(lines) for name, lines in lanes.items()}
print(f"MERGE_OK total={len(ids)} base={len(base)} {lane_counts}")
print(f"grades={dict(grades)} budget_exhausted={budget_exhausted} "
      f"inconclusive_classes={dict(inconclusive_classes)}")
