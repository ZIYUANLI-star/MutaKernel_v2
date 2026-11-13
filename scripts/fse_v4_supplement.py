#!/usr/bin/env python3
"""Supplementary statistics for the authoritative FSE v4 aggregation.

Every quantity here is a re-analysis of the frozen ledgers, manifests, and
annotation tables that ``aggregate_fse_v4.py`` already consumes; nothing is
executed.  The aggregator calls :func:`compute_supplement` and stores the
result under the ``supplement`` key (schema 4.4), so that the manuscript's
Table 4 (witness composition), the fixed-horizon detection columns of
Table 8, the two-case low-precision projection, the yield confidence
intervals of RQ2, the anchor oracle-flip count of RQ1, the host-level control
counts of RQ4, and the blinded-sample composition of §5.8 all derive from the
single aggregation entry point.
"""

from __future__ import annotations

import csv
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Iterable

HORIZONS_S = (60.0, 80.0, 100.0, 120.0)
DIVERGENCE_BUCKETS = (
    ("ge_1", 1.0, math.inf),
    ("0.1_to_1", 0.1, 1.0),
    ("0.01_to_0.1", 0.01, 0.1),
    ("0.001_to_0.01", 0.001, 0.01),
    ("lt_0.001", 0.0, 0.001),
)
REJECTION_SEVERITY = (
    "cuda_runtime",
    "shape_error",
    "interface_binding",
    "other",
    "explicit_dtype_check",
    "dispatch_macro",
    "scalar_type_guard",
)
CURVE_STEP_S = 5.0
CURVE_MAX_S = 300.0


# --------------------------------------------------------------------------
# failure-kind classification
# --------------------------------------------------------------------------

def classify_rejection_message(message: str) -> str:
    text = (message or "").lower()
    if "expected scalar type" in text:
        return "scalar_type_guard"
    if "not implemented for" in text and ("half" in text or "bfloat16" in text):
        return "dispatch_macro"
    if re.search(
        r"missing \d+ required positional argument|takes \d+ positional arguments but|"
        r"got multiple values for argument|is not defined|"
        r"could not convert default argument",
        text,
    ):
        return "interface_binding"
    if re.search(
        r"illegal memory access|misaligned address|device-side assert|"
        r"unspecified launch failure|invalid configuration argument|"
        r"invalid argument|cuda error|cuda kernel failed|cublas|cudnn|out of memory|"
        r"illegal instruction|too many resources|constant memory|packed_accessor",
        text,
    ):
        return "cuda_runtime"
    if re.search(r"shape|size mismatch|dimension|must match|expected input", text):
        return "shape_error"
    if re.search(r"half|bfloat|float|dtype|type", text):
        return "explicit_dtype_check"
    return "other"


def parse_max_abs_error(message: str) -> float | None:
    match = re.search(r"max_abs_error=([^;,\s]+)", message or "")
    if not match:
        return None
    token = match.group(1)
    try:
        return float(token)
    except ValueError:
        lowered = token.lower()
        if "nan" in lowered or "inf" in lowered:
            return math.inf
        return None


def divergence_bucket(value: float) -> str:
    if value == math.inf:
        return "non_finite"
    for name, low, high in DIVERGENCE_BUCKETS:
        if low <= value < high:
            return name
    return "lt_0.001"


def load_task_families(kernelbench_root: Path) -> dict[str, dict]:
    """Map KB_L{level}_P{number} -> file name and whether the reference contains a convolution."""
    families: dict[str, dict] = {}
    for level in (1, 2, 3):
        for path in sorted((kernelbench_root / f"level{level}").glob("*.py")):
            number = path.name.split("_", 1)[0]
            task_id = f"KB_L{level}_P{number}"
            try:
                source = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                source = ""
            families[task_id] = {
                "file": path.name,
                "convolution": bool(re.search(r"conv", source, re.I)),
            }
    return families


# --------------------------------------------------------------------------
# Table 4: composition of the strict witnesses on accepted kernels
# --------------------------------------------------------------------------

def fp32_crash_classes(md_strict: dict, rejected: set[str]) -> dict:
    """Exception classes of the float32-value crash witnesses (rejected kernels)."""
    classes_by_subject: dict[str, set[str]] = defaultdict(set)
    for row in md_strict.values():
        if row.get("validation_status") != "fail":
            continue
        if row.get("mode") != "eval" or (row.get("parameters") or {}):
            continue
        subject_id = str(row["subject_id"])
        if subject_id not in rejected:
            continue
        for error in (row.get("worker_result") or {}).get("errors") or []:
            classes_by_subject[subject_id].add(
                classify_rejection_message(error.get("message") or "")
            )
    dominant: Counter = Counter()
    for classes in classes_by_subject.values():
        dominant[next(c for c in REJECTION_SEVERITY if c in classes)] += 1
    return {"subjects": len(classes_by_subject), "classes": dict(dominant)}


def witness_composition(
    md_strict: dict,
    accepted: set[str],
    value_witness: set[str],
    crash_witness: set[str],
    layer_a: set[str],
    task_of: Callable[[str], str],
    corpus_of: Callable[[str], str],
    task_families: dict[str, dict],
) -> dict:
    accepted_crash = accepted & crash_witness
    accepted_native = accepted & value_witness
    robustness_only = (accepted & layer_a) - value_witness

    # rejection classes, subject-level, most severe class per subject
    classes_by_subject: dict[str, set[str]] = defaultdict(set)
    trigger_rows: Counter = Counter()
    for row in md_strict.values():
        if row.get("validation_status") != "fail":
            continue
        subject_id = str(row["subject_id"])
        if subject_id not in accepted_crash:
            continue
        errors = (row.get("worker_result") or {}).get("errors") or []
        if not errors:
            continue
        params = row.get("parameters") or {}
        trigger_rows[
            f"dtype:{params['dtype']}" if "dtype" in params else str(row.get("mode"))
        ] += 1
        for error in errors:
            classes_by_subject[subject_id].add(
                classify_rejection_message(error.get("message") or "")
            )
    dominant: Counter = Counter()
    for subject_id, classes in classes_by_subject.items():
        dominant[next(c for c in REJECTION_SEVERITY if c in classes)] += 1

    # native-scope divergence profile
    divergence: dict[str, float] = {}
    for row in md_strict.values():
        if (
            row.get("validation_status") != "fail"
            or row.get("mode") != "eval"
            or (row.get("parameters") or {})
        ):
            continue
        subject_id = str(row["subject_id"])
        if subject_id not in accepted_native:
            continue
        worker = row.get("worker_result") or {}
        if worker.get("errors"):
            continue
        oracle = (worker.get("verdict") or {}).get("oracle") or {}
        for mismatch in oracle.get("mismatches") or []:
            message = mismatch.get("message") or ""
            if re.search(r"(NaN|Inf) positions differ", message):
                value = math.inf
            else:
                value = parse_max_abs_error(message)
            if value is None:
                continue
            divergence[subject_id] = max(divergence.get(subject_id, -1.0), value)

    buckets: dict[str, dict[str, int]] = {
        name: {"subjects": 0, "convolution_tasks": 0}
        for name in ("non_finite",) + tuple(b[0] for b in DIVERGENCE_BUCKETS)
    }
    for subject_id, value in divergence.items():
        name = divergence_bucket(value)
        buckets[name]["subjects"] += 1
        if task_families.get(task_of(subject_id), {}).get("convolution"):
            buckets[name]["convolution_tasks"] += 1
    conv_native = {
        s for s in accepted_native
        if task_families.get(task_of(s), {}).get("convolution")
    }
    tolerance_robust = {
        s for s, v in divergence.items() if v == math.inf or v >= 1.0
    }
    legacy_pass_observed = {s for s, v in divergence.items() if v < 0.01}
    tf32_exposed = {
        s for s in conv_native if divergence.get(s, math.inf) != math.inf
    }
    core = tolerance_robust - conv_native
    levels = Counter(task_of(s).split("_")[1] for s in accepted_native)

    return {
        "accepted": len(accepted),
        "accepted_native_witness": len(accepted_native),
        "accepted_rejection_witness": len(accepted_crash),
        "rejection_classes": {
            "scalar_type_guard": dominant.get("scalar_type_guard", 0),
            "dispatch_macro": dominant.get("dispatch_macro", 0),
            "explicit_dtype_check": dominant.get("explicit_dtype_check", 0),
            "cuda_runtime": dominant.get("cuda_runtime", 0),
            "shape_error": dominant.get("shape_error", 0),
            "other": dominant.get("other", 0),
        },
        "rejection_trigger_rows": dict(trigger_rows),
        "robustness_only": len(robustness_only),
        "robustness_only_rejection": len(robustness_only & crash_witness),
        "robustness_only_silent_divergence": len(robustness_only - crash_witness),
        "robustness_only_silent_by_corpus": dict(
            Counter(corpus_of(s) for s in robustness_only - crash_witness)
        ),
        "native_divergence_buckets": buckets,
        "native_with_parsed_divergence": len(divergence),
        "native_on_convolution_tasks": len(conv_native),
        "native_tf32_exposed": len(tf32_exposed),
        "native_tolerance_robust": len(tolerance_robust),
        "native_tolerance_and_tf32_robust_core": len(core),
        "native_legacy_pass_on_observed_case": len(legacy_pass_observed),
        "native_also_rejection_witnessed": len(accepted_native & crash_witness),
        "native_by_level": dict(levels),
        "rules": {
            "convolution_task": "reference source matches /conv/i",
            "tolerance_robust": "non-finite pattern mismatch or max_abs_error >= 1",
            "legacy_pass": "max_abs_error < 0.01 on every native FAIL row (allclose accepts |a-b| < atol)",
            "tf32_exposed": "convolution task with a finite divergence",
        },
    }


# --------------------------------------------------------------------------
# fixed-horizon detections and the two-case projection
# --------------------------------------------------------------------------

def fixed_horizon_detections(
    md: dict,
    contracts: dict,
    strategy_rows: Callable[[dict, str], list],
    cumulative_detection: Callable,
    repairs_by_display: dict[str, dict[str, list]],
    displays: dict[str, str],
) -> dict:
    result = {}
    for strategy_name, display in displays.items():
        merged = repairs_by_display.get(display)
        times, _ = cumulative_detection(
            strategy_rows(md, strategy_name), contracts, merged
        )
        ordered = sorted(times.values())
        grid = [
            CURVE_STEP_S * step
            for step in range(1, int(CURVE_MAX_S / CURVE_STEP_S) + 1)
        ]
        index = 0
        curve = []
        for point in grid:
            while index < len(ordered) and ordered[index] <= point:
                index += 1
            curve.append(index)
        result[display] = {
            "decided_subjects": len(ordered),
            "ttfc_median_s": ordered[len(ordered) // 2] if ordered else None,
            "detected_by": {
                f"{int(h)}s": sum(t <= h for t in ordered) for h in HORIZONS_S
            },
            "curve_grid_s": grid,
            "curve_detected": curve,
        }
    return result


def two_case_projection(md: dict, b6_strategy: str, subjects: int) -> dict:
    """Accounting projection: fp16 seed 0, then bf16 seed 0 if the first case passed."""
    by_subject: dict[str, list] = defaultdict(list)
    for row in md.values():
        if row.get("strategy_name") == b6_strategy:
            by_subject[str(row["subject_id"])].append(row)

    def pick(rows: list, dtype: str) -> dict | None:
        return next(
            (
                r for r in rows
                if (r.get("parameters") or {}).get("dtype") == dtype
                and int(r.get("seed", -1)) == 0
                and r.get("mode") == "eval"
            ),
            None,
        )

    wall_ms = 0.0
    detected: set[str] = set()
    times: list[float] = []
    covered = 0
    for subject_id, rows in by_subject.items():
        first = pick(rows, "float16")
        second = pick(rows, "bfloat16")
        if first is None:
            continue
        covered += 1
        elapsed = float(first.get("parent_wall_ms") or 0.0)
        wall_ms += elapsed
        if first.get("validation_status") == "fail":
            detected.add(subject_id)
            times.append(elapsed / 1000.0)
            continue
        if second is not None:
            t2 = float(second.get("parent_wall_ms") or 0.0)
            wall_ms += t2
            if second.get("validation_status") == "fail":
                detected.add(subject_id)
                times.append((elapsed + t2) / 1000.0)
    times.sort()
    return {
        "subjects_covered": covered,
        "detections": len(detected),
        "total_wall_h": wall_ms / 3.6e6,
        "gpu_s_per_witness": wall_ms / 1000.0 / len(detected) if detected else None,
        "gpu_h_per_1k": wall_ms / 3.6e6 / subjects * 1000.0,
        "ttfc_median_s": times[len(times) // 2] if times else None,
        "detected_at_80s": sum(t <= 80.0 for t in times),
    }


def cost_decomposition(
    md: dict,
    displays: dict[str, str],
    subjects: int,
    detections: dict[str, int],
    total_override_h: dict[str, float],
) -> dict:
    """Split each row's wall-clock into the first invocation and the remainder.

    The first invocation on a subject carries the just-in-time compilation and
    module import of the candidate; every later invocation reuses the compiled
    extension.  ``fixed`` is therefore the compilation-dominated floor that any
    validator pays on this substrate and ``marginal`` is the part attributable
    to the suite itself.
    """
    result = {}
    for strategy_name, display in displays.items():
        by_subject: dict[str, list] = defaultdict(list)
        for row in md.values():
            if row.get("strategy_name") == strategy_name:
                by_subject[str(row["subject_id"])].append(row)
        fixed_ms = 0.0
        ledger_ms = 0.0
        import_ms = 0.0
        first_import_ms = 0.0
        cases = 0
        for rows in by_subject.values():
            rows.sort(key=lambda r: int(r.get("order", 0)))
            for index, row in enumerate(rows):
                wall = float(row.get("parent_wall_ms") or 0.0)
                timings = (row.get("worker_result") or {}).get("timings_ms") or {}
                imported = float(timings.get("candidate_import_ms") or 0.0)
                ledger_ms += wall
                import_ms += imported
                cases += 1
                if index == 0:
                    fixed_ms += wall
                    first_import_ms += imported
        total_h = total_override_h.get(display, ledger_ms / 3.6e6)
        fixed_h = fixed_ms / 3.6e6
        result[display] = {
            "total_h": total_h,
            "fixed_h": fixed_h,
            "marginal_h": total_h - fixed_h,
            "total_per_1k": total_h / subjects * 1000.0,
            "fixed_per_1k": fixed_h / subjects * 1000.0,
            "marginal_per_1k": (total_h - fixed_h) / subjects * 1000.0,
            "gpu_s_per_witness": (
                total_h * 3600.0 / detections[display] if detections.get(display) else None
            ),
            "first_invocation_import_share_pct": (
                100.0 * first_import_ms / fixed_ms if fixed_ms else None
            ),
            "suite_import_share_pct": 100.0 * import_ms / ledger_ms if ledger_ms else None,
            "cases_executed": cases,
        }
    return result


def undecided_causes(md_strict: dict, anchor_rows: dict, subjects: set[str]) -> dict:
    """Cause distribution of undecided verdicts on low-precision cases and the anchor."""

    def classify(reason: str) -> str:
        text = (reason or "").lower()
        if "statesync" in text:
            return "paired_state_alignment"
        if "reference" in text and ("fail" in text or "raise" in text or "error" in text):
            return "reference_failure"
        if "oracle raised" in text:
            return "oracle_error"
        if "timeout" in text:
            return "timeout"
        if "crash" in text:
            return "worker_crash"
        return "other"

    dtype_status: Counter = Counter()
    dtype_causes: Counter = Counter()
    dtype_rows_by_subject: dict[str, list[str]] = defaultdict(list)
    for row in md_strict.values():
        if "dtype" not in (row.get("parameters") or {}):
            continue
        status = str(row.get("validation_status"))
        dtype_status[status] += 1
        subject_id = str(row["subject_id"])
        dtype_rows_by_subject[subject_id].append(status)
        if status == "inconclusive":
            worker = row.get("worker_result") or {}
            dtype_causes[classify(str(worker.get("reason") or ""))] += 1
    never_decided = [
        subject_id
        for subject_id, statuses in dtype_rows_by_subject.items()
        if statuses and all(status == "inconclusive" for status in statuses)
    ]

    by_subject: dict[str, list[dict]] = defaultdict(list)
    for row in anchor_rows.values():
        by_subject[str(row["subject_id"])].append(row)
    undecidable = [
        subject_id
        for subject_id in subjects
        if {str(r.get("validation_status")) for r in by_subject.get(subject_id, [])}
        <= {"inconclusive"}
        and by_subject.get(subject_id)
    ]
    anchor_causes: Counter = Counter()
    anchor_dominant: Counter = Counter()
    for subject_id in undecidable:
        causes = Counter()
        for row in by_subject[subject_id]:
            cause = classify(str((row.get("worker_result") or {}).get("reason") or ""))
            causes[cause] += 1
            anchor_causes[cause] += 1
        anchor_dominant[causes.most_common(1)[0][0]] += 1
    return {
        "dtype_case_status": dict(dtype_status),
        "dtype_undecided_causes": dict(dtype_causes),
        "subjects_with_no_decided_dtype_case": len(never_decided),
        "anchor_undecidable_subjects": len(undecidable),
        "anchor_undecided_case_causes": dict(anchor_causes),
        "anchor_undecidable_dominant_cause": dict(anchor_dominant),
    }


def probe_source_duplicates(probe_ledger_dirs: Iterable[Path]) -> dict:
    """Byte-identical duplicates among the controlled probes (source digests)."""
    import json as _json

    digest_by_subject: dict[str, str] = {}
    for directory in probe_ledger_dirs:
        path = directory / "observations.jsonl"
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = _json.loads(line)
                digest = row.get("subject_sha256")
                if digest:
                    digest_by_subject[str(row["subject_id"])] = str(digest)
    counts = Counter(digest_by_subject.values())
    duplicate_groups = {d: n for d, n in counts.items() if n > 1}
    return {
        "probes_with_digest": len(digest_by_subject),
        "distinct_sources": len(counts),
        "duplicate_groups": len(duplicate_groups),
        "probes_in_duplicate_groups": sum(duplicate_groups.values()),
        "redundant_probes": sum(duplicate_groups.values()) - len(duplicate_groups),
        "largest_group": max(duplicate_groups.values()) if duplicate_groups else 0,
    }


def b6_first_failure_positions(md: dict, b6_strategy: str, b6_detected: set[str]) -> dict:
    by_subject: dict[str, list] = defaultdict(list)
    for row in md.values():
        if row.get("strategy_name") == b6_strategy:
            by_subject[str(row["subject_id"])].append(row)
    positions: Counter = Counter()
    for subject_id, rows in by_subject.items():
        if subject_id not in b6_detected:
            continue
        rows.sort(key=lambda r: int(r.get("order", 0)))
        first = next((r for r in rows if r.get("validation_status") == "fail"), None)
        if first is None:
            positions["no_fail_row"] += 1
            continue
        params = first.get("parameters") or {}
        if "dtype" in params and first.get("mode") == "eval":
            positions[f"{params['dtype']}_seed{int(first.get('seed', -1))}"] += 1
        else:
            positions[f"other:{first.get('mode')}"] += 1
    return dict(positions)


def mdir_plan_positions(md: dict, mdir_strategy: str) -> dict:
    by_subject: dict[str, list] = defaultdict(list)
    for row in md.values():
        if row.get("strategy_name") == mdir_strategy:
            by_subject[str(row["subject_id"])].append(row)
    first_fp16: Counter = Counter()
    first_bf16: Counter = Counter()
    prefix_kinds: Counter = Counter()
    for rows in by_subject.values():
        rows.sort(key=lambda r: int(r.get("order", 0)))
        kinds = []
        for row in rows:
            params = row.get("parameters") or {}
            if params.get("dtype") == "float16":
                kinds.append("fp16")
            elif params.get("dtype") == "bfloat16":
                kinds.append("bf16")
            elif row.get("mode") in ("train", "repeated") or "batch_size" in params:
                kinds.append("diagnostic")
            elif "layout" in params:
                kinds.append("layout")
            else:
                kinds.append("value")
        if "fp16" in kinds:
            index = kinds.index("fp16")
            first_fp16[index + 1] += 1
            prefix_kinds[",".join(sorted(set(kinds[:index])))] += 1
        if "bf16" in kinds:
            first_bf16[kinds.index("bf16") + 1] += 1
    return {
        "subjects_with_rows": len(by_subject),
        "first_fp16_position": {str(k): v for k, v in sorted(first_fp16.items())},
        "first_bf16_position": {str(k): v for k, v in sorted(first_bf16.items())},
        "kinds_before_first_fp16": dict(prefix_kinds),
    }


# --------------------------------------------------------------------------
# RQ2 yield confidence intervals (paired task-cluster bootstrap)
# --------------------------------------------------------------------------

def yield_confidence_intervals(
    rows: dict[str, set[str]],
    pool: set[str],
    task_of: Callable[[str], str],
    baseline: str,
    others: Iterable[str],
    seed: int,
    rounds: int,
) -> dict:
    tasks: dict[str, list[str]] = defaultdict(list)
    for subject_id in pool:
        tasks[task_of(subject_id)].append(subject_id)
    task_list = sorted(tasks)
    rng = random.Random(seed)
    names = [baseline] + [o for o in others if o != baseline]
    samples: dict[str, list[float]] = {name: [] for name in names}
    diffs: dict[str, list[float]] = {name: [] for name in names if name != baseline}
    for _ in range(rounds):
        drawn = [task_list[rng.randrange(len(task_list))] for _ in task_list]
        total = 0
        hits = {name: 0 for name in names}
        for task in drawn:
            for subject_id in tasks[task]:
                total += 1
                for name in names:
                    hits[name] += subject_id in rows[name]
        yields = {name: hits[name] / total for name in names}
        for name in names:
            samples[name].append(yields[name])
        for name in diffs:
            diffs[name].append(yields[baseline] - yields[name])

    def ci(values: list[float]) -> list[float]:
        ordered = sorted(values)
        return [
            100.0 * ordered[int(0.025 * len(ordered))],
            100.0 * ordered[int(0.975 * len(ordered)) - 1],
        ]

    return {
        "pool": len(pool),
        "seed": seed,
        "rounds": rounds,
        "yield_pct": {
            name: {
                "point": 100.0 * len(rows[name] & pool) / len(pool),
                "ci95": ci(samples[name]),
            }
            for name in names
        },
        "difference_pct_points": {
            f"{baseline}_minus_{name}": {
                "point": 100.0 * (len(rows[baseline] & pool) - len(rows[name] & pool)) / len(pool),
                "ci95": ci(diffs[name]),
            }
            for name in diffs
        },
    }


# --------------------------------------------------------------------------
# RQ1 anchor oracle flip, RQ4 host controls, §5.8 sample composition
# --------------------------------------------------------------------------

def anchor_oracle_flip(b1: set[str], b1u: set[str], legacy_covered: set[str]) -> dict:
    b1u_on_covered = b1u & legacy_covered
    return {
        "legacy_covered": len(legacy_covered),
        "B1_rejected": len(b1),
        "B1u_rejected_on_covered": len(b1u_on_covered),
        "B1_only": len(b1 - b1u_on_covered),
        "B1u_only": len(b1u_on_covered - b1),
    }


def host_controls(e1_root: Path) -> dict:
    import json

    controls = json.loads((e1_root / "original_controls.json").read_text(encoding="utf-8"))
    statuses = Counter(str(v.get("status")) for v in controls.values())
    baseline_status: Counter = Counter()
    category_rows: dict[str, Counter] = defaultdict(Counter)
    hosts_with_control_failed: set[str] = set()
    with (e1_root / "baseline_observations.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            status = str(row.get("status"))
            baseline_status[status] += 1
            category_rows[str(row.get("operator_category"))][status] += 1
            if status == "excluded_control_failed":
                hosts_with_control_failed.add(str(row.get("kernel")))
    analyzable_statuses = {"killed", "survived", "machine_proven_equivalent"}
    return {
        "hosts": len(controls),
        "host_control_status": dict(statuses),
        "hosts_with_control_failed_probes": len(hosts_with_control_failed),
        "hosts_analyzable": len(controls) - len(hosts_with_control_failed),
        "probe_status": dict(baseline_status),
        "category_D": {
            "probes": sum(category_rows["D"].values()),
            "analyzable": sum(
                n for s, n in category_rows["D"].items() if s in analyzable_statuses
            ),
            "status": dict(category_rows["D"]),
        },
    }


def instrument1_composition(sampling_csv: Path, labels_csv: Path, md: dict) -> dict:
    test_index = {str(row["test_id"]): row for row in md.values()}
    with sampling_csv.open(encoding="utf-8-sig") as handle:
        units = list(csv.DictReader(handle))
    with labels_csv.open(encoding="utf-8-sig") as handle:
        labels = {row["unit_id"]: row["label"] for row in csv.DictReader(handle)}
    composition: Counter = Counter()
    kind_by_unit: dict[str, str] = {}
    bucket_by_unit: dict[str, str] = {}
    for unit in units:
        if unit.get("family") != "ours":
            continue
        row = test_index.get(unit.get("witness_test_id") or "")
        if row is None:
            composition["not_in_ledger"] += 1
            continue
        errors = (row.get("worker_result") or {}).get("errors") or []
        params = row.get("parameters") or {}
        kind = "crash" if errors else "numeric"
        trigger = "dtype" if "dtype" in params else "fp32"
        composition[f"{kind}_{trigger}"] += 1
        kind_by_unit[unit["unit_id"]] = kind
        if kind == "numeric" and trigger == "fp32":
            worst = None
            oracle = ((row.get("worker_result") or {}).get("verdict") or {}).get("oracle") or {}
            for mismatch in oracle.get("mismatches") or []:
                message = mismatch.get("message") or ""
                value = (
                    math.inf
                    if re.search(r"(NaN|Inf) positions differ", message)
                    else parse_max_abs_error(message)
                )
                if value is not None:
                    worst = value if worst is None else max(worst, value)
            bucket_by_unit[unit["unit_id"]] = (
                divergence_bucket(worst) if worst is not None else "unparsed"
            )
    label_by_kind: Counter = Counter()
    for unit_id, kind in kind_by_unit.items():
        label_by_kind[f"{kind}:{labels.get(unit_id, 'UNLABELED')}"] += 1
    by_bucket: dict[str, Counter] = defaultdict(Counter)
    for unit_id, bucket in bucket_by_unit.items():
        by_bucket[bucket][labels.get(unit_id, "UNLABELED")] += 1
    small = {"lt_0.001", "0.001_to_0.01"}
    sampled_small = sum(sum(c.values()) for b, c in by_bucket.items() if b in small)
    confirmed_small = sum(c.get("CONFIRM", 0) for b, c in by_bucket.items() if b in small)
    return {
        "ours_units": sum(composition.values()),
        "composition": dict(composition),
        "labels_by_kind": dict(label_by_kind),
        "native_numeric_by_divergence": {b: dict(c) for b, c in sorted(by_bucket.items())},
        "native_numeric_below_0.01": {
            "sampled": sampled_small,
            "confirmed": confirmed_small,
        },
    }


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def compute_supplement(
    *,
    md: dict,
    md_strict: dict,
    contracts: dict,
    subjects: set[str],
    rows: dict[str, set[str]],
    accepted_strict: set[str],
    rejected_strict: set[str],
    value_witness: set[str],
    crash_witness: set[str],
    layer_a: set[str],
    legacy_covered: set[str],
    anchor_rows: dict,
    strategy_rows: Callable,
    cumulative_detection: Callable,
    repairs_by_display: dict[str, dict[str, list]],
    strict_cost: dict,
    probe_ledger_dirs: Iterable[Path],
    task_of: Callable[[str], str],
    corpus_of: Callable[[str], str],
    kernelbench_root: Path,
    e1_root: Path,
    sampling_csv: Path,
    labels_csv: Path,
    seed: int,
    rounds: int,
) -> dict:
    task_families = load_task_families(kernelbench_root)
    main_wave = {s for s in subjects if corpus_of(s) in ("C3", "C5")}
    displays = {
        "five-iid-historical-anchor": "B1u",
        "iid-compute-matched": "B3",
        "diversified-value": "B4",
        "boundary-values": "B5",
        "dtype-mode-config": "M-ctx",
        "mutakernel-full": "M-full",
        "mutakernel-directed": "M-dir",
    }
    two_case = two_case_projection(md, "dtype-mode-config", len(subjects))
    costs = cost_decomposition(
        md,
        displays,
        len(subjects),
        {display: len(rows[display]) for display in displays.values()},
        {
            display: strict_cost[display]["wall_h"]
            for display in ("M-full", "M-dir")
            if display in strict_cost
        },
    )
    # The projections reuse the composite arm's own first invocation, so their
    # fixed term is that row's fixed term.
    fixed_h = costs["M-ctx"]["fixed_h"]
    two_case["fixed_h"] = fixed_h
    two_case["marginal_per_1k"] = (
        two_case["total_wall_h"] - fixed_h
    ) / len(subjects) * 1000.0
    return {
        "witness_composition": witness_composition(
            md_strict, accepted_strict, value_witness, crash_witness, layer_a,
            task_of, corpus_of, task_families,
        ),
        "fp32_crash_classes": fp32_crash_classes(md_strict, rejected_strict),
        "cost_decomposition": costs,
        "undecided_causes": undecided_causes(md_strict, anchor_rows, subjects),
        "probe_source_duplicates": probe_source_duplicates(probe_ledger_dirs),
        "fixed_horizon": fixed_horizon_detections(
            md, contracts, strategy_rows, cumulative_detection, repairs_by_display, displays,
        ),
        "two_case_projection": two_case,
        "b6_first_failure_position": b6_first_failure_positions(
            md, "dtype-mode-config", rows["M-ctx"]
        ),
        "mdir_plan_positions": mdir_plan_positions(md, "mutakernel-directed"),
        "yield_ci_main_wave": yield_confidence_intervals(
            rows, main_wave, task_of, "M-full", ("B3", "B4", "B5", "M-ctx"), seed, rounds
        ),
        "anchor_oracle_flip": anchor_oracle_flip(rows["B1"], rows["B1u"], legacy_covered),
        "host_controls": host_controls(e1_root),
        "instrument1_composition": instrument1_composition(sampling_csv, labels_csv, md),
        "horizons_s": list(HORIZONS_S),
    }
