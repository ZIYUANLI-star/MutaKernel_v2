"""Remote-side: re-grade the 8 environmental INCONCLUSIVEs offline.

Rescued (resource-degraded completion) records are updated in place with a
``regraded_from`` marker; the rest are archived to
cse_observations_env_v1.jsonl, removed from their lane obs + completed
checkpoints, and thereby requeued.  Originals of rescued records are also
kept in the archive.
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/mk_v2")
from scripts.run_e1_cse_falsify import grade_cse_evidence  # noqa: E402

E1 = Path("/root/mk_v2_runs/e1")
ARCHIVE = E1 / "cse_observations_env_v1.jsonl"
NOW = datetime.now(timezone.utc).isoformat()

if ARCHIVE.exists():
    raise SystemExit("REFUSE: env archive exists; reprocess already ran")

rescued, requeued = [], []
archive_lines = []
for lane in (3, 4, 5):
    obs = E1 / f"cse_observations_lane{lane}.jsonl"
    done = E1 / f"cse_completed_lane{lane}.json"
    if not obs.exists():
        continue
    kept, removed_ids = [], []
    changed = False
    for line in open(obs, encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("outcome") != "INCONCLUSIVE":
            kept.append(line if line.endswith("\n") else line + "\n")
            continue
        pseudo = {
            "validation_status": row.get("validation_status", "inconclusive"),
            "trials": row.get("trials") or [],
            "divergence": row.get("divergence"),
        }
        status, outcome, evidence = grade_cse_evidence(
            pseudo, timed_out=bool(row.get("timed_out")))
        archive_lines.append(line if line.endswith("\n") else line + "\n")
        changed = True
        if outcome == "STILL_LIKELY_EQUIVALENT":
            row.update({
                "outcome": outcome, "validation_status": status,
                "inconclusive_class": None, "evidence": evidence,
                "regraded_at": NOW,
                "regraded_from": "INCONCLUSIVE:environmental_voided_rounds",
            })
            kept.append(json.dumps(row) + "\n")
            rescued.append((lane, row["probe_id"]))
        else:
            removed_ids.append(row["probe_id"])
            requeued.append((lane, row["probe_id"]))
    if changed:
        shutil.copy2(obs, str(obs) + ".bak_envfix")
        with open(obs, "w", encoding="utf-8") as fh:
            fh.writelines(kept)
        if removed_ids and done.exists():
            shutil.copy2(done, str(done) + ".bak_envfix")
            ids = set(json.load(open(done)))
            done.write_text(json.dumps(sorted(ids - set(removed_ids))))

with open(ARCHIVE, "w", encoding="utf-8") as fh:
    fh.writelines(archive_lines)

print(f"rescued ({len(rescued)}):", rescued)
print(f"requeued ({len(requeued)}):", requeued)

# account check over the whole CSE campaign
likely = set()
for line in open(E1 / "equiv_observations.jsonl", encoding="utf-8"):
    row = json.loads(line)
    if row.get("evidence_grade") == "LIKELY_EQUIVALENT":
        likely.add(row["probe_id"])
done_all = set()
for f in sorted(E1.glob("cse_completed_lane*.json")):
    done_all |= set(json.load(open(f)))
legacy = E1 / "cse_falsify_completed.json"
if legacy.exists():
    done_all |= set(json.load(open(legacy)))
print(f"CSE account: targets={len(likely)} done={len(likely & done_all)} "
      f"pending={len(likely - done_all)} sum={len(likely)}")
print("ENV_REPROCESS_OK")
