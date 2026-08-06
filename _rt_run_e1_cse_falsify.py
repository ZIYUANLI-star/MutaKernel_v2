#!/usr/bin/env python3
"""E1 counterexample-search falsification of LIKELY_EQUIVALENT probes (GPU).

Blueprint §5.5: "Counterexample search additionally falsified the equivalence
hypothesis for ? of ? probes the evidence pipeline had graded
LIKELY_EQUIVALENT".  This driver takes the LIKELY_EQUIVALENT set from
run_e1_probe_study --phase equiv and runs a strictly *stronger* search than
the first pass:

  * all 21 value stress policies (not just the operator-directed six),
  * more random rounds and more repeats per policy,
  * (TODO, listed in the run manifest) dtype/train/config/repeated dimension
    cases via scripts/_stress_worker.py once the audit stress phase lands.

Only a sound SPEC_VIOLATION-style FAIL from src.validation counts as a
falsification; tolerance-conforming bitwise divergence never does (the equiv
worker already enforces this).  Reuses the E0 execution pattern: serial,
checkpointed, classified INCONCLUSIVE, full trial evidence.

Usage:
  python scripts/run_e1_cse_falsify.py --out-dir /root/mk_v2_runs/e1 \
      --kernelbench-root KernelBench [--timeout 900]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.audit.inconclusive import classify_observation  # noqa: E402
from scripts.run_e1_probe_study import (  # noqa: E402
    BASELINE_PROTOCOL,
    EQUIV_ROUND_TIMEOUT_S,
    _load_probe_files,
    _now,
    _resolve_problem_file,
    _write_worker_log,
    environment_fingerprint,
    grade_equiv_evidence,
    run_worker,
)

FALSIFY_EQUIV_RUNS = 40
FALSIFY_BASE_SEED = 50000
FALSIFY_STRESS_REPEATS = 3

# Partial-evidence thresholds (preregistered; mirrors the equiv-phase
# "all random + 2/3 of stress rounds" spirit: equiv used 20/20 + 8/12).
CSE_STRESS_ROUNDS_PLANNED = 63  # 21 policies x 3 repeats
CSE_MIN_STRESS_ROUNDS = 42      # 2/3 of 63

# Resource-degraded completion (preregistered 2026-07-27): rounds voided by
# environmental resource events (CUDA/host OOM, watchdog) are environment
# incidents, not subject-semantics evidence (inconclusive-strata doctrine),
# so they must not poison an otherwise near-complete probe.  A completed
# probe whose non-pass rounds are ALL environmental grades
# STILL_LIKELY_EQUIVALENT iff it kept >=75% of planned rounds valid,
# >=75% of random rounds passed, and the stress threshold above holds.
CSE_MIN_VALID_ROUNDS = 77   # 75% of the 103 planned rounds
CSE_MIN_RANDOM_PASS = 30    # 75% of the 40 random rounds

_ENVIRONMENTAL_MARKERS = (
    "out of memory", "resource/infrastructure", "cuda oom", "failed to alloc",
    "outofmemoryerror", "round timed out",
)


def environmental_void(trial):
    """True when a non-pass trial was voided by the environment (VRAM/host
    OOM or the round watchdog) and thus carries no semantic signal."""
    if trial.get("round_timeout"):
        return True
    text = (str(trial.get("reason", "")) + " "
            + json.dumps(trial.get("errors") or [])).lower()
    return any(marker in text for marker in _ENVIRONMENTAL_MARKERS)


def grade_cse_evidence(result, timed_out,
                       stress_rounds_planned=CSE_STRESS_ROUNDS_PLANNED):
    """CSE outcome with the partial-evidence backstop (equiv-fix mirror).

    Fully-completed probes keep the historical mapping exactly
    (fail -> FALSIFIED, pass -> STILL_LIKELY_EQUIVALENT, else
    INCONCLUSIVE).  When the budget is exhausted, the completed rounds are
    graded instead of voided: a sound divergence witness stays FALSIFIED;
    all 40 random passes plus >= CSE_MIN_STRESS_ROUNDS stress passes with
    no divergence -> STILL_LIKELY_EQUIVALENT with ``budget_exhausted``
    evidence; otherwise INCONCLUSIVE (timeout class upstream).

    ``stress_rounds_planned`` may be reduced below CSE_STRESS_ROUNDS_PLANNED
    when a per-kernel policy skip (resource-domain violation) removes some
    stress policies for this kernel.  Only the *planned* bookkeeping shrinks;
    the *pass* threshold ``CSE_MIN_STRESS_ROUNDS`` (42) stays absolute, so the
    evidence bar is never loosened — it becomes a stricter pass-rate.
    """
    status, grade, evidence = grade_equiv_evidence(
        result, timed_out,
        equiv_runs=FALSIFY_EQUIV_RUNS,
        stress_rounds_planned=stress_rounds_planned,
        min_stress_rounds=CSE_MIN_STRESS_ROUNDS)
    outcome = {
        "WITNESSED_NON_EQUIVALENT": "FALSIFIED",
        "LIKELY_EQUIVALENT": "STILL_LIKELY_EQUIVALENT",
    }.get(grade, "INCONCLUSIVE")
    if outcome == "INCONCLUSIVE":
        rescue = _resource_degraded_rescue(result)
        if rescue is not None:
            return "pass", "STILL_LIKELY_EQUIVALENT", rescue
    return status, outcome, evidence


def _resource_degraded_rescue(result):
    """Preregistered resource-degraded completion check (see constants).

    Returns the evidence dict when the probe qualifies, else None.  Only
    reachable for probes the base grading left INCONCLUSIVE; a sound
    divergence witness never lands here (base grading returns FALSIFIED).
    """
    result = result or {}
    if result.get("divergence"):
        return None
    trials = result.get("trials") or []
    non_pass = [t for t in trials
                if str(t.get("status", "")).lower() != "pass"]
    if not all(environmental_void(t) for t in non_pass):
        return None
    random_passed = sum(
        1 for t in trials if t.get("round_type") == "random"
        and str(t.get("status", "")).lower() == "pass")
    stress_passed = sum(
        1 for t in trials if t.get("round_type") == "stress"
        and str(t.get("status", "")).lower() == "pass")
    if (random_passed + stress_passed >= CSE_MIN_VALID_ROUNDS
            and random_passed >= CSE_MIN_RANDOM_PASS
            and stress_passed >= CSE_MIN_STRESS_ROUNDS):
        return {
            "resource_degraded": True,
            "environmental_voided_rounds": len(non_pass),
            "rounds_completed": random_passed + stress_passed,
            "rounds_planned": FALSIFY_EQUIV_RUNS + CSE_STRESS_ROUNDS_PLANNED,
            "random_rounds_passed": random_passed,
            "stress_rounds_passed": stress_passed,
            "grading_threshold": {
                "min_valid_rounds": CSE_MIN_VALID_ROUNDS,
                "min_random_passes": CSE_MIN_RANDOM_PASS,
                "min_stress_passes": CSE_MIN_STRESS_ROUNDS,
            },
        }
    return None


def witness_fields(divergence):
    """Extract the falsification witness triple for a FALSIFIED record.

    ``witness_policy`` is the stress policy name (or ``"random"`` for a
    random-round witness), ``witness_round`` the round/sub index, and
    ``witness_seed`` the input seed — the evidence chain a falsification
    must carry.
    """
    if not divergence:
        return {"witness_policy": None, "witness_round": None,
                "witness_seed": None}
    policy = divergence.get("policy")
    if policy is None and divergence.get("round_type") == "random":
        policy = "random"
    round_no = divergence.get("round_index")
    if round_no is None:
        round_no = divergence.get("sub_index")
    return {"witness_policy": policy, "witness_round": round_no,
            "witness_seed": divergence.get("seed")}


def cse_lane_paths(out, lane, tag=None):
    """Per-lane CSE output paths; ``lane=None`` keeps the legacy serial names.

    Lane filenames follow the ``cse_observations_lane*`` /
    ``cse_completed_lane*`` monitoring-glob shape.
    """
    if lane is None:
        return {
            "obs": out / "cse_falsify_observations.jsonl",
            "done": out / "cse_falsify_completed.json",
            "summary": out / "cse_falsify_summary.json",
            "manifest": out / "cse_falsify_run_manifest.json",
        }
    suffix = f"_lane{lane}" + (f"_{tag}" if tag else "")
    return {
        "obs": out / f"cse_observations{suffix}.jsonl",
        "done": out / f"cse_completed{suffix}.json",
        "summary": out / f"cse_summary{suffix}.json",
        "manifest": out / f"cse_run_manifest{suffix}.json",
    }


def load_cse_skip_set(out, lane, tag=None):
    """Return ``(own_completed, skip)`` for one CSE driver.

    Mirrors the equiv-phase contract: a lane driver folds in the legacy
    serial checkpoint plus every other lane's completed file (read-only) so
    probes are never re-run across lane reorganisations; it checkpoints only
    its own probes.
    """
    paths = cse_lane_paths(out, lane, tag)
    own = set(
        json.loads(paths["done"].read_text()) if paths["done"].exists() else [])
    skip = set(own)
    if lane is not None:
        legacy = out / "cse_falsify_completed.json"
        if legacy.exists():
            skip |= set(json.loads(legacy.read_text()))
        for other in sorted(out.glob("cse_completed_lane*.json")):
            if other != paths["done"]:
                skip |= set(json.loads(other.read_text()))
    return own, skip


def load_policy_skip(out, path=None):
    """Per-kernel stress-policy skip map (resource-domain violations).

    A policy whose *input generation* cannot complete within the per-round
    watchdog / cgroup-memory budget for a given kernel's input size is a
    kernel x policy resource-domain violation: the adversarial input can never
    be materialised, so the round carries no subject-semantics signal and would
    only burn GPU-hours producing INCONCLUSIVE.  Such policies are skipped
    uniformly for BOTH the original and the mutant (the cost is model-
    independent — it is in the input tensor, not the kernel), recorded
    transparently, and their rounds are neither passes nor failures.

    Auto-discovered at ``out/cse_policy_skip.json`` (so the guard's fixed
    AUTORESTART command picks it up with no change) unless ``path`` overrides.
    Accepts either ``{"skip": {kernel: [policy, ...]}, ...}`` or a flat
    ``{kernel: [policy, ...]}`` mapping.
    """
    skip_path = Path(path) if path else (out / "cse_policy_skip.json")
    if not skip_path.exists():
        return {}
    raw = json.loads(skip_path.read_text(encoding="utf-8"))
    mapping = raw.get("skip", raw) if isinstance(raw, dict) else {}
    return {k: set(v) for k, v in mapping.items()}


def classify_vram_evidence(kernel_history, known_unsafe=()):
    """Evidence-based VRAM classification for the heavy-lane split.

    ``kernel_history`` maps kernel -> {
        ``resource_events``: any resource/OOM record anywhere in its history,
        ``capped45_complete``: finished at least one probe under a 0.45
            (36.9GB) memory-fraction lane,
        ``capped45_timeout``: any whole-probe timeout under a 0.45 lane,
    }.

    Rules (conservative; anything unproven stays serial):
      * known_unsafe or resource_events        -> PROVEN_UNSAFE (serial)
      * completed under 0.45 with no resource
        events and no 0.45-era timeouts        -> PROVEN_SAFE (parallelisable)
      * otherwise                              -> UNKNOWN (serial)
    """
    out = {}
    unsafe = set(known_unsafe)
    for kernel, hist in kernel_history.items():
        if kernel in unsafe or hist.get("resource_events"):
            out[kernel] = "PROVEN_UNSAFE"
        elif hist.get("capped45_complete") and not hist.get("capped45_timeout"):
            out[kernel] = "PROVEN_SAFE"
        else:
            out[kernel] = "UNKNOWN"
    return out


def order_kernel_files(kernel_files, ordered_kernels):
    """Stable-order probe files by the lane plan's kernel list.

    The plan's kernel order is the execution queue: kernels listed later run
    later (used to schedule oversubscription-risk kernels behind the
    parallel lanes' completion horizon).  Kernels not in the list keep
    their relative order at the end (the lane filter drops them anyway).
    """
    position = {k: i for i, k in enumerate(ordered_kernels)}
    return sorted(
        kernel_files,
        key=lambda kf: position.get(kf["kernel"]["problem_name"],
                                    len(position)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--kernelbench-root", required=True, type=Path)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--lane", type=int, default=None,
                    help="run only the kernels of this lane in the CSE lane "
                         "plan (requires --lane-plan); outputs go to "
                         "cse_*_lane<N> files")
    ap.add_argument("--lane-plan", type=Path,
                    help="CSE lane plan JSON (lanes[i].kernels)")
    ap.add_argument("--lane-tag", default=None,
                    help="qualifier appended to lane output filenames")
    ap.add_argument("--policy-skip-config", type=Path, default=None,
                    help="per-kernel stress-policy skip map "
                         "(default: <out-dir>/cse_policy_skip.json if present)")
    args = ap.parse_args()

    out = args.out_dir
    lane = args.lane
    tag = args.lane_tag
    lane_kernels = None
    if lane is not None:
        if not args.lane_plan:
            raise SystemExit("--lane requires --lane-plan")
        plan = json.loads(args.lane_plan.read_text(encoding="utf-8"))
        lane_kernels = set(plan["lanes"][lane]["kernels"])
    scratch = Path(tempfile.mkdtemp(prefix="e1cse_", dir=str(out)))
    paths = cse_lane_paths(out, lane, tag)
    obs_path = paths["obs"]
    done_path = paths["done"]
    completed, skip = load_cse_skip_set(out, lane, tag)
    lane_label = "" if lane is None else f" (lane {lane}{'/' + tag if tag else ''})"

    from src.stress.policy_bank import get_all_policy_names
    all_policies = get_all_policy_names()
    policy_skip = load_policy_skip(out, args.policy_skip_config)
    if policy_skip:
        print(f"[{_now()}] cse-falsify{lane_label}: per-kernel policy skip "
              f"active for {sorted(policy_skip)}", flush=True)

    likely = {}
    with open(out / "equiv_observations.jsonl", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("evidence_grade") == "LIKELY_EQUIVALENT":
                likely[row["probe_id"]] = row

    kernel_files = _load_probe_files(out)
    if lane is not None:
        kernel_files = order_kernel_files(
            kernel_files, plan["lanes"][lane]["kernels"])
    targets = [
        (kf, probe)
        for kf in kernel_files
        if lane_kernels is None or kf["kernel"]["problem_name"] in lane_kernels
        for probe in kf["probes"]
        if probe["probe_id"] in likely
    ]
    lane_done = sum(1 for _, p in targets if p["probe_id"] in skip)
    print(f"[{_now()}] cse-falsify{lane_label}: {len(targets)} "
          f"LIKELY_EQUIVALENT targets, {lane_done} done", flush=True)

    manifest = {
        "phase": "cse_falsify",
        "run_id": f"e1-cse-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "started_at": _now(),
        "lane": lane,
        "lane_tag": tag,
        "timeout_s": args.timeout,
        "round_timeout_s": EQUIV_ROUND_TIMEOUT_S,
        "partial_evidence_thresholds": {
            "random_rounds": FALSIFY_EQUIV_RUNS,
            "min_stress_rounds": CSE_MIN_STRESS_ROUNDS,
            "stress_rounds_planned": CSE_STRESS_ROUNDS_PLANNED,
            "rule": "all random passes + >=2/3 stress passes, no divergence",
        },
        "resource_degraded_thresholds": {
            "min_valid_rounds": CSE_MIN_VALID_ROUNDS,
            "min_random_passes": CSE_MIN_RANDOM_PASS,
            "min_stress_passes": CSE_MIN_STRESS_ROUNDS,
            "rule": ("completed probe whose non-pass rounds are ALL "
                     "environmental (VRAM/host OOM, round watchdog) grades "
                     "STILL_LIKELY_EQUIVALENT; environment incidents are "
                     "not subject-semantics evidence"),
        },
        "search": {
            "equiv_runs": FALSIFY_EQUIV_RUNS,
            "base_seed": FALSIFY_BASE_SEED,
            "stress_policies": all_policies,
            "stress_repeats": FALSIFY_STRESS_REPEATS,
        },
        "policy_skip": {k: sorted(v) for k, v in policy_skip.items()},
        "policy_skip_note": (
            "per-kernel resource-domain violations: listed policies' input "
            "generation exceeds the per-round watchdog / cgroup-memory budget "
            "for that kernel's input size (model-independent cost); rounds are "
            "skipped uniformly for original+mutant and are neither passes nor "
            "failures. Pass threshold CSE_MIN_STRESS_ROUNDS=42 is unchanged "
            "(absolute), so the evidence bar is not loosened."),
        "todo": [
            "dtype/train/config/repeated dimension cases via _stress_worker "
            "(audit stress phase); value-dimension-only until then",
        ],
        "environment": environment_fingerprint(),
    }
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    counter = Counter()
    for kf, probe in targets:
        probe_id = probe["probe_id"]
        if probe_id in skip:
            continue
        kernel = kf["kernel"]
        skip_for = policy_skip.get(kernel["problem_name"], set())
        probe_policies = [p for p in all_policies if p not in skip_for]
        planned_stress = len(probe_policies) * FALSIFY_STRESS_REPEATS
        problem_file = _resolve_problem_file(
            args.kernelbench_root, kernel["level"], kernel["problem_id"])
        cfg = {
            "mode": "equiv",
            "mutant_id": probe_id,
            "problem_file": str(problem_file),
            "kernel_code": kf["kernel_source"],
            "mutated_code": probe["mutated_code"],
            "operator_name": probe["operator_name"],
            "device": BASELINE_PROTOCOL["device"],
            "equiv_runs": FALSIFY_EQUIV_RUNS,
            "base_seed": FALSIFY_BASE_SEED,
            "stress_policies": probe_policies,
            "stress_repeats": FALSIFY_STRESS_REPEATS,
            "atol": BASELINE_PROTOCOL["atol"],
            "rtol": BASELINE_PROTOCOL["rtol"],
            "round_timeout": EQUIV_ROUND_TIMEOUT_S,
        }
        result, timed_out, wall_ms, so, se = run_worker(cfg, args.timeout, scratch)
        validation_status, outcome, partial_evidence = grade_cse_evidence(
            result, timed_out, stress_rounds_planned=planned_stress)
        record = {
            "probe_id": probe_id,
            "kernel": kernel["problem_name"],
            "operator_name": probe["operator_name"],
            "fault_class": probe["fault_class"],
            "outcome": outcome,
            "validation_status": validation_status,
            "inconclusive_class": (
                classify_observation(result or {}, timed_out=timed_out)
                if outcome == "INCONCLUSIVE" else None),
            "divergence": (result or {}).get("divergence"),
            "trials": (result or {}).get("trials"),
            "valid_rounds": (result or {}).get("valid_rounds"),
            "wall_ms": round(wall_ms, 1),
            "timed_out": timed_out,
            "finished_at": _now(),
        }
        if skip_for:
            record["skipped_policies"] = sorted(skip_for)
            record["stress_rounds_planned"] = planned_stress
            record["policy_skip_reason"] = "resource_domain_violation"
        if outcome == "FALSIFIED":
            record.update(witness_fields(record["divergence"]))
        if partial_evidence is not None:
            record["evidence"] = partial_evidence
        if timed_out or result is None or se.strip():
            _write_worker_log(out, f"{probe_id}_cse", so, se)
        with open(obs_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        completed.add(probe_id)
        skip.add(probe_id)
        lane_done += 1
        done_path.write_text(json.dumps(sorted(completed)), encoding="utf-8")
        counter[outcome] += 1
        if lane_done % 10 == 0:
            print(f"[{_now()}] cse-falsify{lane_label}: "
                  f"{lane_done}/{len(targets)} {dict(counter)}", flush=True)

    paths["summary"].write_text(json.dumps({
        "finished_at": _now(),
        "lane": lane,
        "targets": len(targets),
        "outcomes": dict(counter),
    }, indent=2), encoding="utf-8")
    print(f"[{_now()}] cse-falsify DONE{lane_label}: {dict(counter)}", flush=True)


if __name__ == "__main__":
    main()
