"""Per-kernel stress-policy skip for CSE (resource-domain violations).

Pins two invariants of the lane3 P53 remediation:
  1. the skip map is auto-discovered / parsed from both accepted JSON shapes
     and the per-probe policy list drops exactly the skipped policies;
  2. reducing the *planned* stress rounds must NOT loosen the grade: the
     absolute pass threshold CSE_MIN_STRESS_ROUNDS (42) still governs, so a
     probe passing 41 stress rounds is INCONCLUSIVE even when only 54 rounds
     were planned (41/54 = 76% would clear a proportional 2/3 bar but must
     still fail the preregistered absolute bar).

Torch-free, CPU-only.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_e1_cse_falsify import (
    CSE_MIN_STRESS_ROUNDS,
    FALSIFY_EQUIV_RUNS,
    FALSIFY_STRESS_REPEATS,
    grade_cse_evidence,
    load_policy_skip,
)


def _cse_trials(random_pass=0, stress_pass=0):
    trials = [{"round_type": "random", "round_index": i, "status": "pass"}
              for i in range(random_pass)]
    trials += [{"round_type": "stress", "sub_index": i, "status": "pass"}
               for i in range(stress_pass)]
    return trials


# --- skip-map loading / parsing -------------------------------------------

def test_load_policy_skip_absent_returns_empty(tmp_path: Path):
    assert load_policy_skip(tmp_path) == {}


def test_load_policy_skip_nested_shape(tmp_path: Path):
    (tmp_path / "cse_policy_skip.json").write_text(json.dumps(
        {"skip": {"L1_P53": ["mixed_extremes", "sparse"]}, "reason": "x"}))
    skip = load_policy_skip(tmp_path)
    assert skip == {"L1_P53": {"mixed_extremes", "sparse"}}


def test_load_policy_skip_flat_shape_and_explicit_path(tmp_path: Path):
    p = tmp_path / "custom_skip.json"
    p.write_text(json.dumps({"L1_P53": ["sparse_extreme"]}))
    skip = load_policy_skip(tmp_path, p)
    assert skip == {"L1_P53": {"sparse_extreme"}}


def test_per_probe_policies_drop_skipped_only():
    all_policies = ["large_magnitude", "mixed_extremes", "sparse",
                    "near_zero", "sparse_extreme", "all_positive"]
    skip_for = {"mixed_extremes", "sparse", "sparse_extreme"}
    probe_policies = [p for p in all_policies if p not in skip_for]
    assert probe_policies == ["large_magnitude", "near_zero", "all_positive"]
    assert set(probe_policies).isdisjoint(skip_for)
    # planned rounds shrink proportionally with the repeat count
    planned = len(probe_policies) * FALSIFY_STRESS_REPEATS
    assert planned == 3 * FALSIFY_STRESS_REPEATS


# --- grading is not loosened by a reduced planned count --------------------

def _reduced_planned(n_skipped_policies):
    return (21 - n_skipped_policies) * FALSIFY_STRESS_REPEATS  # 21 total policies


def test_reduced_planned_still_requires_absolute_42():
    # 42 stress passes clears the absolute bar -> STILL_LIKELY_EQUIVALENT.
    planned = _reduced_planned(3)  # 18 policies * 3 = 54 rounds planned
    assert planned == 54
    result = {"partial": True, "validation_status": "inconclusive",
              "trials": _cse_trials(FALSIFY_EQUIV_RUNS, CSE_MIN_STRESS_ROUNDS)}
    status, outcome, evidence = grade_cse_evidence(
        result, timed_out=True, stress_rounds_planned=planned)
    assert (status, outcome) == ("pass", "STILL_LIKELY_EQUIVALENT")
    assert evidence["rounds_planned"] == FALSIFY_EQUIV_RUNS + planned
    assert evidence["grading_threshold"]["stress"] == CSE_MIN_STRESS_ROUNDS


def test_reduced_planned_does_not_lower_threshold():
    # 41 stress passes would clear a *proportional* 2/3-of-54=36 bar but must
    # still fail the preregistered absolute bar of 42 -> INCONCLUSIVE.
    planned = _reduced_planned(3)
    result = {"partial": True, "validation_status": "inconclusive",
              "trials": _cse_trials(FALSIFY_EQUIV_RUNS, CSE_MIN_STRESS_ROUNDS - 1)}
    status, outcome, _ = grade_cse_evidence(
        result, timed_out=True, stress_rounds_planned=planned)
    assert (status, outcome) == ("inconclusive", "INCONCLUSIVE")


def test_reduced_planned_clean_complete_is_still_likely():
    # A probe that completes all remaining rounds cleanly (no watchdog, not
    # partial) keeps the historical fast path: pass -> STILL_LIKELY_EQUIVALENT.
    planned = _reduced_planned(3)
    result = {"validation_status": "pass",
              "trials": _cse_trials(FALSIFY_EQUIV_RUNS, planned)}
    status, outcome, evidence = grade_cse_evidence(
        result, timed_out=False, stress_rounds_planned=planned)
    assert (status, outcome) == ("pass", "STILL_LIKELY_EQUIVALENT")
    assert evidence is None


def test_reduced_planned_witness_still_falsified():
    planned = _reduced_planned(3)
    result = {"partial": True, "validation_status": "inconclusive",
              "divergence": {"detail": "output_diverged"},
              "trials": _cse_trials(FALSIFY_EQUIV_RUNS, 10)}
    status, outcome, _ = grade_cse_evidence(
        result, timed_out=True, stress_rounds_planned=planned)
    assert (status, outcome) == ("fail", "FALSIFIED")
