"""Remote-side: offline re-grade of lane0's 1800s-timeout CSE records,
falsification-witness backfill, and rebuild of split lanes 3/4/5.

1. Re-grade every INCONCLUSIVE(timeout) record in cse_observations_lane0
   from its stored trials via grade_cse_evidence (preregistered thresholds:
   40/40 random + >=42/63 stress, no divergence).  Originals are archived
   to cse_observations_lane0_timeout_v1.jsonl; passing records are updated
   in place (regraded_from marker); failing ones leave the obs file and the
   lane0 checkpoint -> rerun queue.
2. Backfill witness_policy/round/seed on any FALSIFIED record where they
   are missing/null (from its stored divergence).
3. Rebuild plan lanes[3..5] from post-regrade remaining probes so requeued
   kernels (e.g. P16/P19) are covered again; PROVEN_SAFE from the stored
   vram_classification; per-probe estimate min(3600, equiv_median x 3.22).
"""
import json
import shutil
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/mk_v2")
from scripts.run_e1_cse_falsify import grade_cse_evidence, witness_fields  # noqa: E402
from scripts.run_e1_probe_study import plan_equiv_lanes  # noqa: E402

E1 = Path("/root/mk_v2_runs/e1")
NOW = datetime.now(timezone.utc).isoformat()

# ---------------------------------------------------------------- 1. regrade
obs0 = E1 / "cse_observations_lane0.jsonl"
done0 = E1 / "cse_completed_lane0.json"
archive = E1 / "cse_observations_lane0_timeout_v1.jsonl"
if archive.exists():
    raise SystemExit("REFUSE: regrade archive exists; already ran")
shutil.copy2(obs0, str(obs0) + ".bak_regrade")
shutil.copy2(done0, str(done0) + ".bak_regrade")

kept, archived, requeue_ids = [], [], []
dist = {"regraded_STILL": 0, "requeue_below_threshold": 0, "untouched": 0}
stress_pass_hist = []
for line in open(obs0, encoding="utf-8"):
    if not line.strip():
        continue
    row = json.loads(line)
    is_timeout_inc = (row.get("outcome") == "INCONCLUSIVE"
                      and row.get("timed_out") is True
                      and row.get("inconclusive_class") == "timeout")
    if not is_timeout_inc:
        kept.append(line if line.endswith("\n") else line + "\n")
        dist["untouched"] += 1
        continue
    archived.append(line if line.endswith("\n") else line + "\n")
    pseudo = {
        "validation_status": row.get("validation_status", "inconclusive"),
        "trials": row.get("trials") or [],
        "divergence": row.get("divergence"),
        "partial": True,
    }
    status, outcome, evidence = grade_cse_evidence(pseudo, timed_out=True)
    stress_pass_hist.append(evidence["stress_rounds_passed"])
    if outcome == "STILL_LIKELY_EQUIVALENT":
        row.update({
            "outcome": outcome,
            "validation_status": status,
            "inconclusive_class": None,
            "evidence": evidence,
            "regraded_at": NOW,
            "regraded_from": "INCONCLUSIVE:timeout(1800s budget)",
        })
        kept.append(json.dumps(row) + "\n")
        dist["regraded_STILL"] += 1
    else:
        requeue_ids.append(row["probe_id"])
        dist["requeue_below_threshold"] += 1

with open(archive, "w", encoding="utf-8") as fh:
    fh.writelines(archived)
with open(obs0, "w", encoding="utf-8") as fh:
    fh.writelines(kept)
ids0 = set(json.load(open(done0)))
done0.write_text(json.dumps(sorted(ids0 - set(requeue_ids))))
print(f"regrade: {dist}; archived={len(archived)}")
print("stress_rounds_passed histogram of the 36:",
      dict(sorted(__import__('collections').Counter(stress_pass_hist).items())))
print("requeue ids:", requeue_ids)

# ------------------------------------------------------- 2. witness backfill
backfilled = []
for path in sorted(E1.glob("cse_observations_lane*.jsonl")) + [
        E1 / "cse_falsify_observations.jsonl"]:
    if not path.exists() or path == archive:
        continue
    rows, changed = [], False
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        if (row.get("outcome") == "FALSIFIED"
                and not row.get("witness_policy")):
            row.update(witness_fields(row.get("divergence")))
            row["witness_backfilled_at"] = NOW
            backfilled.append((path.name, row["probe_id"],
                               row["witness_policy"], row["witness_round"],
                               row["witness_seed"]))
            changed = True
            rows.append(json.dumps(row) + "\n")
        else:
            rows.append(line if line.endswith("\n") else line + "\n")
    if changed:
        shutil.copy2(path, str(path) + ".bak_witnessfix")
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(rows)
print("witness backfilled:", backfilled)

# ------------------------------------------------- 3. rebuild lanes 3/4/5
plan_path = E1 / "cse_lane_plan.json"
plan = json.loads(plan_path.read_text(encoding="utf-8"))
classes = {k: v["class"] for k, v in plan["vram_classification"].items()}
lane0_kernels = set(plan["lanes"][0]["kernels"])

likely_by_kernel = {}
for line in open(E1 / "equiv_observations.jsonl", encoding="utf-8"):
    row = json.loads(line)
    if (row.get("evidence_grade") == "LIKELY_EQUIVALENT"
            and row["kernel"] in lane0_kernels):
        likely_by_kernel.setdefault(row["kernel"], set()).add(row["probe_id"])
cse_done = set()
for f in sorted(E1.glob("cse_completed_lane*.json")):
    cse_done |= set(json.load(open(f)))
legacy = E1 / "cse_falsify_completed.json"
if legacy.exists():
    cse_done |= set(json.load(open(legacy)))

remaining = {k: sorted(p for p in pids if p not in cse_done)
             for k, pids in likely_by_kernel.items()}
remaining = {k: v for k, v in remaining.items() if v}
total = sum(len(p) for p in likely_by_kernel.values())
done_count = total - sum(len(v) for v in remaining.values())

loads = {}
for k, pids in remaining.items():
    med = plan["per_kernel"][k]["equiv_wall_median_s"]
    loads[k] = min(3600.0, med * 3.22) * len(pids)
serial = sorted((k for k in remaining if classes[k] != "PROVEN_SAFE"),
                key=lambda k: (-loads[k], k))
safe_loads = {k: loads[k] for k in remaining if classes[k] == "PROVEN_SAFE"}
par, par_totals = plan_equiv_lanes(safe_loads, [], n_lanes=2)
lanes = [serial, par[0], par[1]]
totals = [sum(loads[k] for k in serial), par_totals[0], par_totals[1]]
flat = [k for lane in lanes for k in lane]
assert len(flat) == len(set(flat)) and set(flat) == set(remaining)
assert done_count + sum(len(remaining[k]) for k in flat) == total == 206

roles = ["heavy-serial-v2 (0.92)", "safe-parallel (0.45)", "safe-parallel (0.45)"]
for i in range(3):
    plan["lanes"][3 + i] = {
        "lane": 3 + i,
        "role": roles[i],
        "kernels": lanes[i],
        "kernel_count": len(lanes[i]),
        "probe_count": sum(len(remaining[k]) for k in lanes[i]),
        "est_seconds": round(totals[i], 1),
        "est_hours": round(totals[i] / 3600, 2),
        "split_from": 0,
        "timeout_s": 3600,
    }
plan["version"] = 3
plan["v3_created_at"] = NOW
plan["v3_note"] = ("post-regrade rebuild: 3600s budget, partial-evidence "
                   "backstop, requeued below-threshold timeouts included")
plan_path.write_text(json.dumps(plan, indent=1), encoding="utf-8")

print(f"\nlane0 CSE account: total=206 done={done_count} "
      f"pending={sum(len(v) for v in remaining.values())}")
for entry in plan["lanes"][3:]:
    print(f"lane {entry['lane']} ({entry['role']}): "
          f"kernels={entry['kernel_count']} probes={entry['probe_count']} "
          f"est={entry['est_hours']}h")
print(f"split ETA = max({totals[0]/3600:.1f}, {totals[1]/3600:.1f}, "
      f"{totals[2]/3600:.1f}) h")
print("REGRADE_OK")
