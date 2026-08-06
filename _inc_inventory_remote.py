"""Remote-side READ-ONLY inventory of every INCONCLUSIVE record under
/root/mk_v2_runs/e1 (active + archived), with a dry-run re-grade of each
archived CSE record through the currently deployed preregistered
grade_cse_evidence (base thresholds + resource_degraded rescue), plus the
lanes-3/4/5 requeue reconciliation and a dump of the guard script.

Writes JSON to /root/mk_v2_runs/e1/_inc_inventory_report.json; mutates nothing.
"""
import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/root/mk_v2")
from scripts.run_e1_cse_falsify import (  # noqa: E402
    grade_cse_evidence, environmental_void, _resource_degraded_rescue)

E1 = Path("/root/mk_v2_runs/e1")
report = {"files": {}, "inconclusive": [], "reconcile": {}, "guard": {},
          "manifests": {}}


def trial_summary(row):
    trials = row.get("trials") or []
    by = Counter((t.get("round_type") or "?",
                  str(t.get("status", "?")).lower()) for t in trials)
    non_pass = [t for t in trials
                if str(t.get("status", "")).lower() != "pass"]
    env_void = sum(1 for t in non_pass if environmental_void(t))
    reasons = []
    for t in non_pass[:3]:
        r = str(t.get("reason", ""))[:160]
        if t.get("round_timeout"):
            r = "[round_timeout] " + r
        reasons.append(r)
    return {
        "n_trials": len(trials),
        "by_type_status": {f"{k[0]}/{k[1]}": v for k, v in sorted(by.items())},
        "random_pass": by.get(("random", "pass"), 0),
        "stress_pass": by.get(("stress", "pass"), 0),
        "non_pass": len(non_pass),
        "env_void_of_non_pass": env_void,
        "non_pass_reasons_sample": reasons,
        "valid_rounds": row.get("valid_rounds"),
        "divergence": bool(row.get("divergence")),
    }


# ---------------------------------------------------------------- scan files
patterns = ["equiv_observations*.jsonl", "cse_observations*.jsonl",
            "cse_falsify_observations.jsonl"]
paths = sorted({p for pat in patterns for p in E1.glob(pat)})
for path in paths:
    n_lines, n_inc = 0, 0
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        n_lines += 1
        row = json.loads(line)
        outcome = row.get("outcome") or row.get("evidence_grade")
        if outcome != "INCONCLUSIVE":
            continue
        n_inc += 1
        rec = {
            "file": path.name,
            "probe_id": row.get("probe_id"),
            "kernel": row.get("kernel"),
            "phase": "equiv" if path.name.startswith("equiv") else "cse",
            "outcome": outcome,
            "inconclusive_class": row.get("inconclusive_class"),
            "timed_out": row.get("timed_out"),
            "wall_ms": row.get("wall_ms"),
            "trial_summary": trial_summary(row),
        }
        if rec["phase"] == "cse":
            pseudo = {
                "validation_status": row.get("validation_status",
                                             "inconclusive"),
                "trials": row.get("trials") or [],
                "divergence": row.get("divergence"),
                "valid_rounds": row.get("valid_rounds"),
                "partial": True,
            }
            try:
                st, oc, ev = grade_cse_evidence(
                    pseudo, timed_out=bool(row.get("timed_out")))
                rec["regrade_dryrun"] = {"outcome": oc, "status": st,
                                         "evidence": ev}
            except Exception as exc:  # never fail the inventory
                rec["regrade_dryrun"] = {"error": f"{type(exc).__name__}: {exc}"}
        report["inconclusive"].append(rec)
    report["files"][path.name] = {"lines": n_lines, "inconclusive": n_inc}

# ------------------------------------------------------------- reconcile 206
plan = json.loads((E1 / "cse_lane_plan.json").read_text())
lane0_kernels = set(plan["lanes"][0]["kernels"])
likely_all, likely_lane0 = {}, set()
for line in open(E1 / "equiv_observations.jsonl", encoding="utf-8"):
    row = json.loads(line)
    if row.get("evidence_grade") == "LIKELY_EQUIVALENT":
        likely_all[row["probe_id"]] = row["kernel"]
        if row["kernel"] in lane0_kernels:
            likely_lane0.add(row["probe_id"])

completed = {}
for f in sorted(E1.glob("cse_completed_lane*.json")) + \
        [E1 / "cse_falsify_completed.json"]:
    if f.exists():
        completed[f.name] = sorted(json.load(open(f)))
done_union = {p for ids in completed.values() for p in ids}

# active per-lane observed probe ids (dup check across active lanes)
obs_ids = {}
for path in sorted(E1.glob("cse_observations_lane*.jsonl")):
    if "_v1" in path.name:   # archives excluded from active account
        continue
    ids = []
    for line in open(path, encoding="utf-8"):
        if line.strip():
            ids.append(json.loads(line)["probe_id"])
    obs_ids[path.name] = ids
flat = [p for ids in obs_ids.values() for p in ids]
dup_across = [p for p, n in Counter(flat).items() if n > 1]

pending = likely_lane0 - done_union
lane_pending = {}
for i in (3, 4, 5):
    lk = set(plan["lanes"][i]["kernels"])
    lane_pending[i] = sorted(p for p in pending if likely_all[p] in lk)
covered = set().union(*[set(v) for v in lane_pending.values()]) \
    if lane_pending else set()

# archived probe ids and where they stand now
arch_status = {}
for name in ("cse_observations_lane0_timeout_v1.jsonl",
             "cse_observations_env_v1.jsonl"):
    path = E1 / name
    if not path.exists():
        continue
    entries = []
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        pid = json.loads(line)["probe_id"]
        entries.append({
            "probe_id": pid,
            "in_done_union": pid in done_union,
            "in_pending_345": pid in covered,
            "lane": next((i for i in (3, 4, 5)
                          if pid in lane_pending[i]), None),
        })
    arch_status[name] = entries

report["reconcile"] = {
    "lane0_targets": len(likely_lane0),
    "done": len(likely_lane0 & done_union),
    "pending": len(pending),
    "sum_check_206": len(likely_lane0 & done_union) + len(pending),
    "pending_not_covered_by_345": sorted(pending - covered),
    "lane_pending_counts": {i: len(v) for i, v in lane_pending.items()},
    "lane_pending_ids": lane_pending,
    "completed_files": {k: len(v) for k, v in completed.items()},
    "dup_probe_ids_across_active_obs": dup_across,
    "global_targets_all_lanes": len(likely_all),
    "archived_probe_status": arch_status,
    "plan_lane_meta": [
        {k: v for k, v in plan["lanes"][i].items() if k != "kernels"}
        for i in range(len(plan["lanes"]))],
}

# --------------------------------------------------------------- guard state
gpath = Path("/root/mk_v2_runs/e1_guard.sh")
report["guard"]["script"] = gpath.read_text(encoding="utf-8") \
    if gpath.exists() else None
pidf = Path("/root/mk_v2_runs/e1_guard.pid")
report["guard"]["pid"] = pidf.read_text().strip() if pidf.exists() else None
report["guard"]["pid_alive"] = False
if report["guard"]["pid"]:
    try:
        os.kill(int(report["guard"]["pid"]), 0)
        report["guard"]["pid_alive"] = True
    except (ProcessLookupError, ValueError, PermissionError):
        pass
glog = Path("/root/mk_v2_runs/e1_guard.log")
if glog.exists():
    tail = glog.read_text(encoding="utf-8", errors="replace").splitlines()
    report["guard"]["log_tail"] = tail[-15:]
else:
    report["guard"]["log_tail"] = None
report["guard"]["ps"] = os.popen(
    "ps -eo pid,args | grep -E 'run_e1_cse_falsify|e1_guard' "
    "| grep -v grep").read().splitlines()
report["guard"]["done_markers"] = sorted(
    os.path.basename(p) for p in glob.glob(str(E1 / "CSE_DONE_LANE*")))

for i in (3, 4, 5):
    mf = E1 / f"cse_run_manifest_lane{i}.json"
    if mf.exists():
        m = json.loads(mf.read_text())
        report["manifests"][i] = {
            k: m.get(k) for k in
            ("run_id", "started_at", "timeout_s", "round_timeout_s",
             "partial_evidence_thresholds", "resource_degraded_thresholds")}

out = E1 / "_inc_inventory_report.json"
out.write_text(json.dumps(report, indent=1), encoding="utf-8")
print(f"wrote {out} inconclusive_total={len(report['inconclusive'])}")
print("INVENTORY_OK")
