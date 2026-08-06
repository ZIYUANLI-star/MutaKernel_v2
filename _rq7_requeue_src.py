#!/usr/bin/env python3
"""Production requeue of the 7 REQUEUE_THEN_GRADE probes from wc1_report
(2026-08-01), per the advisor ruling of 2026-07-31.

Probes and protocol fidelity:
  * L1_P37__const_perturb__{2,3,7}, L1_P37__mask_boundary__0 (equiv):
    production equiv protocol (equiv_runs=20, base_seed=10000, repeats=2)
    with the two poisoned positions (sparse_extreme, boundary_last_element)
    removed from the directed policy list per ruling 1.  Threshold stays
    stress_pass>=8 (absolute) over the reduced 10-round stress plan.
  * L1_P49__sync_remove__0, L2_P63__sync_remove__1 (equiv): unmodified
    production protocol (worker-directed 6 policies x 2).
  * L1_P96__relop_replace__8 (CSE): production CSE protocol (equiv_runs=40,
    base_seed=50000, all 21 policies x 3, no skip for this kernel).

Results are written to /root/mk_v2_runs/e1/requeue_final/ and DO NOT touch
the production ledgers; the one-shot auditable amendment happens separately.
"""
import json
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

MK = Path("/root/mk_v2")
E1 = Path("/root/mk_v2_runs/e1")
OUT = E1 / "requeue_final"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "run.log"

sys.path.insert(0, str(MK))
import scripts.run_e1_probe_study as ps  # noqa: E402
from scripts._mutant_worker import OPERATOR_DIRECTED_POLICIES  # noqa: E402
from scripts.run_e1_cse_falsify import grade_cse_evidence  # noqa: E402

POISONED_P37 = {"sparse_extreme", "boundary_last_element"}
CSE_ALL_POLICIES = [
    "large_magnitude", "near_overflow", "near_zero", "denormals",
    "all_negative", "all_positive", "mixed_extremes", "alternating_sign",
    "sparse", "uniform_constant", "structured_ramp", "boundary_last_element",
    "head_heavy", "tail_heavy", "relop_boundary_hit", "extreme_magnitude",
    "near_epsilon", "reduction_adversarial", "init_sensitive",
    "dense_nonzero", "sparse_extreme",
]

# (probe_id, stage, exclude_poisoned, budget_s) -- light first, P96 last
TARGETS = [
    ("L2_P63__sync_remove__1",   "equiv", False, 3600),
    ("L1_P37__const_perturb__2", "equiv", True,  3600),
    ("L1_P37__const_perturb__3", "equiv", True,  3600),
    ("L1_P37__const_perturb__7", "equiv", True,  3600),
    ("L1_P37__mask_boundary__0", "equiv", True,  3600),
    ("L1_P49__sync_remove__0",   "equiv", False, 3600),
    ("L1_P96__relop_replace__8", "cse",   False, 5400),
]


def now():
    return datetime.now(timezone.utc).isoformat()


def log(msg):
    line = "[%s] %s" % (now(), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main():
    manifest = {
        "run_id": "requeue_final-%s" % datetime.now().strftime("%Y%m%d-%H%M%S"),
        "started_at": now(),
        "basis": "wc1_report regrade_plan (generated 2026-08-01T07:33) + "
                 "advisor ruling WC1_20260731",
        "poisoned_positions_L1_P37": sorted(POISONED_P37),
        "targets": [t[0] for t in TARGETS],
        "protocols": {
            "equiv": {"equiv_runs": 20, "base_seed": 10000,
                      "stress_repeats": 2, "round_timeout_s": 90,
                      "threshold": "random_pass>=20 and stress_pass>=8"},
            "cse": {"equiv_runs": 40, "base_seed": 50000,
                    "stress_repeats": 3, "round_timeout_s": 90,
                    "threshold": "valid>=77 and random_pass>=30 and "
                                 "stress_pass>=42"},
        },
        "note": "production ledgers untouched; results feed the one-shot "
                "auditable ledger amendment",
        "environment": ps.environment_fingerprint(),
    }
    (OUT / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    completed_path = OUT / "completed.json"
    completed = set(json.loads(completed_path.read_text())) \
        if completed_path.exists() else set()

    probe_files = ps._load_probe_files(E1)
    probe_index = {}
    for kf in probe_files:
        for probe in kf["probes"]:
            probe_index[probe["probe_id"]] = (kf, probe)

    scratch = Path(tempfile.mkdtemp(prefix="rq7_", dir=str(OUT)))
    obs_path = OUT / "observations.jsonl"

    for probe_id, stage, exclude, budget in TARGETS:
        if probe_id in completed:
            log("%s already completed, skip" % probe_id)
            continue
        kf, probe = probe_index[probe_id]
        kernel = kf["kernel"]
        problem_file = ps._resolve_problem_file(
            MK / "KernelBench", kernel["level"], kernel["problem_id"])
        cfg = {
            "mode": "equiv",
            "mutant_id": probe_id,
            "problem_file": str(problem_file),
            "kernel_code": kf["kernel_source"],
            "mutated_code": probe["mutated_code"],
            "operator_name": probe["operator_name"],
            "device": ps.BASELINE_PROTOCOL["device"],
            "atol": ps.BASELINE_PROTOCOL["atol"],
            "rtol": ps.BASELINE_PROTOCOL["rtol"],
            "round_timeout": ps.EQUIV_ROUND_TIMEOUT_S,
        }
        if stage == "cse":
            cfg.update({"equiv_runs": 40, "base_seed": 50000,
                        "stress_policies": list(CSE_ALL_POLICIES),
                        "stress_repeats": 3})
            planned_stress = len(CSE_ALL_POLICIES) * 3
        else:
            cfg.update({"equiv_runs": 20, "base_seed": 10000})
            directed = OPERATOR_DIRECTED_POLICIES.get(
                probe["operator_name"], None)
            if exclude:
                directed = [p for p in (directed or [])
                            if p not in POISONED_P37]
                cfg["stress_policies"] = directed
                cfg["stress_repeats"] = 2
            planned_stress = (len(directed) * 2) if directed is not None \
                else ps.EQUIV_STRESS_ROUNDS_PLANNED

        log("start %s stage=%s planned_stress=%d budget=%ds%s"
            % (probe_id, stage, planned_stress, budget,
               " (poisoned positions excluded)" if exclude else ""))
        result, timed_out, wall_ms, so, se = ps.run_worker(
            cfg, budget, scratch)
        if stage == "cse":
            validation_status, outcome, evidence = grade_cse_evidence(
                result, timed_out, stress_rounds_planned=planned_stress)
        else:
            validation_status, outcome, evidence = ps.grade_equiv_evidence(
                result, timed_out, stress_rounds_planned=planned_stress,
                min_stress_rounds=ps.EQUIV_MIN_STRESS_ROUNDS)
        record = {
            "probe_id": probe_id,
            "kernel": kernel["problem_name"],
            "kernel_id": "L%s_P%s" % (kernel["level"], kernel["problem_id"]),
            "stage": stage,
            "operator_name": probe["operator_name"],
            "fault_class": probe["fault_class"],
            "requeue_reason": "wc1 regrade REQUEUE_THEN_GRADE",
            "poisoned_excluded": sorted(POISONED_P37) if exclude else [],
            "planned_stress_rounds": planned_stress,
            "outcome": outcome,
            "validation_status": validation_status,
            "evidence": evidence,
            "divergence": (result or {}).get("divergence"),
            "trials": (result or {}).get("trials"),
            "valid_rounds": (result or {}).get("valid_rounds"),
            "round_timeouts": (result or {}).get("round_timeouts"),
            "errors": (result or {}).get("errors"),
            "wall_ms": round(wall_ms, 1),
            "timed_out": timed_out,
            "worker_budget_s": budget,
            "finished_at": now(),
        }
        if timed_out or result is None or se.strip():
            (OUT / ("%s.workerlog" % probe_id)).write_text(
                "STDOUT:\n%s\n\nSTDERR:\n%s\n" % (so, se), encoding="utf-8")
        with open(obs_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        completed.add(probe_id)
        completed_path.write_text(json.dumps(sorted(completed)))
        log("done %s outcome=%s valid_rounds=%s wall=%.0fs timed_out=%s"
            % (probe_id, outcome, record["valid_rounds"],
               wall_ms / 1000.0, timed_out))

    # summary
    rows = [json.loads(line) for line in open(obs_path, encoding="utf-8")]
    latest = {}
    for r in rows:
        latest[r["probe_id"]] = r
    summary = {
        "finished_at": now(),
        "outcomes": {pid: {"outcome": r["outcome"],
                           "valid_rounds": r["valid_rounds"],
                           "timed_out": r["timed_out"],
                           "divergence": bool(r.get("divergence"))}
                     for pid, r in sorted(latest.items())},
    }
    (OUT / "run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "RQ7_DONE").write_text(now())
    log("ALL DONE: %s" % json.dumps(summary["outcomes"]))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("FATAL:\n%s" % traceback.format_exc())
        (OUT / "RQ7_BLOCKED").write_text(traceback.format_exc())
        raise
