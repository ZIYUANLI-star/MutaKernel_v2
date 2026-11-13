#!/usr/bin/env python3
"""Authoritative FSE aggregation from frozen ledgers, contracts, and repairs.

This entry point replaces the pre-contract ``agg_v3.py``.  It invokes the real
``assert_case_in_contract`` predicate for every shared-substrate observation,
keeps functional and heterogeneous evidence layers separate, incorporates the
minimal suffix-repair campaign, derives Dtype-8 from the uncensored M-ctx
prefix, and emits machine-readable table inputs with source-file hashes.

Schema 4.3 adds the ``supplement`` block (``fse_v4_supplement.py``): witness
composition by failure kind and divergence magnitude (manuscript Table 4),
fixed-horizon detections (Table 8), the two-case low-precision projection,
paired task-cluster yield CIs, the anchor oracle-flip count, host-level control
counts of the probe study, and the composition of the blinded witness sample.

Schema 4.5 (2026-09-06) splits every robustness-only count by failure kind
(``robustness_only_rejection`` / ``robustness_only_silent_divergence``) so that
manuscript Table 3, whose robustness-only column was divided into two
mutually exclusive columns, is transcribed directly from the aggregation
rather than derived from the supplement.  No value changes.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_minimal_repair_campaign import repair_rows  # noqa: E402
from build_minimal_repair_campaign import (  # noqa: E402
    case_is_in_contract,
    read_json,
)
from fse_v4_supplement import compute_supplement  # noqa: E402
from src.experiments.manifest import sha256_file, stable_json_sha256  # noqa: E402


SEED = 20260819
BOOTSTRAP_ROUNDS = 10_000
PERMUTATION_ROUNDS = 20_000

OUR_STRATEGIES = {
    "five-iid-historical-anchor": "B1u",
    "iid-compute-matched": "B3",
    "diversified-value": "B4",
    "boundary-values": "B5",
    "dtype-mode-config": "M-ctx",
    "mutakernel-full": "M-full",
    "mutakernel-directed": "M-dir",
}


def corpus(subject_id: str) -> str:
    return subject_id.split("__", 1)[0]


def task(subject_id: str) -> str:
    parts = subject_id.split("__")
    return parts[1] if len(parts) > 1 else subject_id


def by_corpus(subjects: Iterable[str]) -> dict[str, int]:
    return dict(Counter(corpus(subject) for subject in subjects))


def read_jsonl(paths: Iterable[Path], strategy_names: set[str] | None = None) -> dict:
    rows = {}
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if strategy_names and row.get("strategy_name") not in strategy_names:
                    continue
                key = (
                    str(row["subject_id"]),
                    str(row.get("strategy_name")),
                    str(row["test_id"]),
                )
                previous = rows.get(key)
                if previous is None or (
                    previous.get("validation_status") != "fail"
                    and row.get("validation_status") == "fail"
                ):
                    rows[key] = row
    return rows


def load_contracts(manifests: Iterable[Path]) -> tuple[dict, dict]:
    contracts = {}
    meta = {}
    for path in manifests:
        manifest = read_json(path)
        for subject in manifest["subjects"]:
            subject_id = str(subject["subject_id"])
            contracts[subject_id] = subject["contract"]
            meta[subject_id] = {
                "dataset": subject["dataset"],
                "task_id": subject["task_id"],
            }
    return contracts, meta


def strict_rows(rows: dict, contracts: dict) -> dict:
    return {
        key: row
        for key, row in rows.items()
        if case_is_in_contract(row, contracts[str(row["subject_id"])])
    }


def fail_set(rows: Iterable[dict]) -> set[str]:
    return {
        str(row["subject_id"])
        for row in rows
        if row.get("validation_status") == "fail"
    }


def strategy_rows(rows: dict, strategy_name: str) -> list[dict]:
    return [
        row for row in rows.values() if row.get("strategy_name") == strategy_name
    ]


def scan_ports(base_dirs: list[Path], name: str) -> set[str]:
    detected = set()
    for directory in base_dirs:
        for path in directory.glob(f"{name}_*_summary.json"):
            summary = read_json(path)
            statuses = summary.get("statuses") or {}
            fail = statuses.get("FAIL", statuses.get("fail", 0))
            if isinstance(fail, list):
                fail = len(fail)
            if int(fail or 0) > 0:
                detected.add(str(summary["subject_id"]))
    return detected


def scan_b11(directories: list[Path]) -> set[str]:
    detected = set()
    for directory in directories:
        for path in directory.glob("*/b11_result.json"):
            result = read_json(path)
            if any(
                int(tool.get("error_count") or 0) > 0
                or int(tool.get("hazard_count") or 0) > 0
                for tool in (result.get("tools") or [])
            ):
                detected.add(str(result["subject_id"]))
    return detected


def repair_detection_sets(campaign_dir: Path) -> dict[str, set[str]]:
    index = read_json(campaign_dir / "campaign_index.json")
    result: dict[str, set[str]] = defaultdict(set)
    for lane in index["lanes"]:
        if not lane["groups"]:
            continue
        observations, _ = repair_rows(campaign_dir, lane)
        for row in observations:
            if row.get("validation_status") != "fail":
                continue
            if lane["lane"].startswith("mdir-"):
                result["M-dir"].add(str(row["subject_id"]))
            elif lane["lane"].startswith("mfull-"):
                result["M-full"].add(str(row["subject_id"]))
            elif lane["lane"].startswith("mlegacy-"):
                result["M-legacy"].add(str(row["subject_id"]))
            elif lane["lane"] == "lodo":
                result["LODO"].add(str(row["subject_id"]))
    return result


def repair_rows_by_subject(campaign_dir: Path, display: str) -> dict[str, list[dict]]:
    """Minimal-repair suffix cases for one display row, keyed by subject."""
    index = read_json(campaign_dir / "campaign_index.json")
    prefix = {"M-full": "mfull-", "M-dir": "mdir-", "M-legacy": "mlegacy-"}[display]
    result: dict[str, list[dict]] = defaultdict(list)
    for lane in index["lanes"]:
        if not lane["groups"] or not lane["lane"].startswith(prefix):
            continue
        observations, _ = repair_rows(campaign_dir, lane)
        for row in observations:
            result[str(row["subject_id"])].append(row)
    return result


def streak_repair_observations(campaign_dir: Path) -> list[dict]:
    """Every observation of the timeout-streak budget repair, with its source row."""
    index = read_json(campaign_dir / "campaign_index.json")
    merged: list[dict] = []
    for lane in index["lanes"]:
        for group in lane["groups"]:
            source_map = read_json(campaign_dir / group["source_test_map"].replace("\\", "/"))
            by_test_id = {}
            for subject_id, mappings in source_map.items():
                for mapping in mappings:
                    by_test_id[str(mapping["repair_case"]["test_id"])] = {
                        "subject_id": subject_id,
                        "source_order": int(mapping["source_order"]),
                        "source_test_id": str(mapping["source_test_id"]),
                    }
            path = (
                campaign_dir
                / "results"
                / lane["lane"]
                / group["group_id"]
                / "observations.jsonl"
            )
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    source = by_test_id[str(row["test_id"])]
                    merged.append(
                        {
                            **row,
                            **source,
                            "display_row": OUR_STRATEGIES[group["source_strategy"]],
                        }
                    )
    return merged


def streak_detection_sets(campaign_dir: Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for row in streak_repair_observations(campaign_dir):
        if row.get("validation_status") == "fail":
            result[row["display_row"]].add(str(row["subject_id"]))
    return result


def streak_rows_by_subject(campaign_dir: Path, display: str) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = defaultdict(list)
    for row in streak_repair_observations(campaign_dir):
        if row["display_row"] == display:
            result[str(row["subject_id"])].append(row)
    return result


def cumulative_detection(
    rows: list[dict],
    contracts: dict,
    repair_by_subject: dict[str, list[dict]] | None = None,
) -> tuple[dict[str, float], float]:
    by_subject: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_subject[str(row["subject_id"])].append(row)
    times = {}
    total_wall_ms = 0.0
    for subject_id, subject_rows in by_subject.items():
        cumulative = 0.0
        found = False
        for row in sorted(subject_rows, key=lambda value: int(value.get("order", 0))):
            wall = float(row.get("parent_wall_ms") or 0.0)
            total_wall_ms += wall
            cumulative += wall
            if (
                row.get("validation_status") == "fail"
                and case_is_in_contract(row, contracts[subject_id])
            ):
                times[subject_id] = cumulative / 1000.0
                found = True
                break
        if not found and repair_by_subject:
            for row in sorted(
                repair_by_subject.get(subject_id, []),
                key=lambda value: int(value["source_order"]),
            ):
                wall = float(row.get("parent_wall_ms") or 0.0)
                cumulative += wall
                if row.get("validation_status") == "fail":
                    times[subject_id] = cumulative / 1000.0
                    break
    return times, total_wall_ms


def task_cluster_bootstrap_ci(
    detected: set[str], pool: set[str], rounds: int = BOOTSTRAP_ROUNDS
) -> tuple[float, float]:
    subjects_by_task: dict[str, list[str]] = defaultdict(list)
    for subject in pool:
        subjects_by_task[task(subject)].append(subject)
    tasks = sorted(subjects_by_task)
    rng = random.Random(SEED)
    estimates = []
    for _ in range(rounds):
        sampled = [rng.choice(tasks) for _ in tasks]
        denominator = sum(len(subjects_by_task[item]) for item in sampled)
        numerator = sum(
            sum(subject in detected for subject in subjects_by_task[item])
            for item in sampled
        )
        estimates.append(100.0 * numerator / denominator)
    estimates.sort()
    return (
        estimates[int(0.025 * rounds)],
        estimates[min(rounds - 1, int(0.975 * rounds))],
    )


def task_signflip_p(
    left: set[str], right: set[str], pool: set[str], rounds: int = PERMUTATION_ROUNDS
) -> float:
    differences: dict[str, int] = defaultdict(int)
    for subject in pool:
        differences[task(subject)] += int(subject in left) - int(subject in right)
    values = [value for value in differences.values() if value]
    observed = abs(sum(values))
    if not values:
        return 1.0
    rng = random.Random(SEED)
    extreme = 0
    for _ in range(rounds):
        statistic = abs(
            sum(value if rng.random() < 0.5 else -value for value in values)
        )
        extreme += statistic >= observed
    return (extreme + 1) / (rounds + 1)


def row_record(name: str, detected: set[str], pool: set[str]) -> dict:
    ci = task_cluster_bootstrap_ci(detected, pool)
    return {
        "detected_full": len(detected),
        "detected_by_corpus": by_corpus(detected),
        "detected_in_pool": len(detected & pool),
        "coverage_pct": 100.0 * len(detected & pool) / len(pool),
        "task_cluster_bootstrap_95ci": list(ci),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--fetched-root", required=True, type=Path)
    parser.add_argument("--repair-campaign", required=True, type=Path)
    parser.add_argument("--repair-summary", required=True, type=Path)
    parser.add_argument(
        "--streak-repair",
        required=True,
        type=Path,
        help=(
            "Timeout-streak budget repair campaign: restores the documented "
            "full-budget semantics for rows the mid-campaign breaker truncated"
        ),
    )
    parser.add_argument("--p3-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--kernelbench-root",
        type=Path,
        default=PROJECT_ROOT / "KernelBench" / "KernelBench",
        help="KernelBench task sources (level1/2/3) used to classify convolution tasks",
    )
    parser.add_argument(
        "--e1-root",
        type=Path,
        default=PROJECT_ROOT
        / "MutakernelV2" / "实验" / "重跑实验数据" / "离线分析" / "data" / "e1",
        help="frozen probe-study baseline (original_controls.json, baseline_observations.jsonl)",
    )
    parser.add_argument(
        "--instrument1-dir",
        type=Path,
        default=PROJECT_ROOT / "MutakernelV2" / "人工标注" / "仪器1_见证盲审_Table11",
        help="blinded witness re-adjudication sampling list and locked labels",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = args.data_root.resolve()
    fetched = args.fetched_root.resolve()
    manifests = [
        data / "cardc/e3_campaign/wave1_subject_manifest_v2.json",
        data / "cardc/e3_campaign/wave2_subject_manifest.json",
        fetched / "b/wave3_subject_manifest.json",
    ]
    contracts, meta = load_contracts(manifests)
    md_paths = [
        data / "root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl",
        data / "cardc/e3_campaign/wave15/lane_d_run/observations.jsonl",
        data / "w23/wave2/lane_m2_run/observations.jsonl",
        data / "w23/wave2/lane_d2_run/observations.jsonl",
        data / "w23/wave3/lane_m3_run/observations.jsonl",
        data / "w23/wave3/lane_d3_run/observations.jsonl",
    ]
    md = read_jsonl(md_paths, set(OUR_STRATEGIES))
    md_strict = strict_rows(md, contracts)

    rows: dict[str, set[str]] = {}
    for strategy_name, display in OUR_STRATEGIES.items():
        rows[display] = fail_set(strategy_rows(md_strict, strategy_name))

    # Legacy oracle rows.
    g_paths = [
        Path(path)
        for path in glob.glob(
            str(
                data
                / "root/mk_v2_runs/e3_campaign/wave15/lane_g_run_shard*/observations.jsonl"
            )
        )
        + glob.glob(
            str(data / "w23/wave2/lane_g2_run_shard*/observations.jsonl")
        )
    ]
    g = read_jsonl(g_paths)
    g_strict = strict_rows(g, contracts)
    rows["B1"] = fail_set(strategy_rows(g_strict, "five-iid-historical-anchor"))
    rows["M-legacy"] = fail_set(strategy_rows(g_strict, "mutakernel-full"))

    # Repair detections: censoring-suffix repair, then timeout-streak budget repair.
    repair_sets = repair_detection_sets(args.repair_campaign.resolve())
    rows["M-full"] |= repair_sets.get("M-full", set())
    rows["M-dir"] |= repair_sets.get("M-dir", set())
    rows["M-legacy"] |= repair_sets.get("M-legacy", set())
    streak_dir = args.streak_repair.resolve()
    streak_sets = streak_detection_sets(streak_dir)
    for display, detected in streak_sets.items():
        rows[display] |= detected
    rows["Dtype-8"] = set(rows["M-ctx"])

    p3 = args.p3_root.resolve()
    port_dirs = {
        "B7": [
            data / "cardc/e3_campaign/wave15/lane_p_b7",
            data / "cardc/e3_campaign/wave2/lane_p2_b7",
            p3 / "lane_p3_b7",
        ],
        "B8": [
            data / "cardc/e3_campaign/wave15/lane_p_b8",
            data / "cardc/e3_campaign/wave2/lane_p2_b8",
            p3 / "lane_p3_b8",
        ],
        "B9": [
            data / "cardc/e3_campaign/wave15/lane_p_b9",
            data / "cardc/e3_campaign/wave2/lane_p2_b9",
            p3 / "lane_p3_b9",
        ],
    }
    for name, directories in port_dirs.items():
        rows[name] = scan_ports(directories, name.lower())
    rows["B11"] = scan_b11(
        [
            data / "b11_w15/wave15/lane_p_b11",
            data / "cardc/e3_campaign/wave2/lane_p2_b11",
            p3 / "lane_p3_b11",
        ]
    )

    subjects = set(meta)
    layer_a = set().union(
        *(rows[name] for name in ("B1u", "B3", "B4", "B5", "M-ctx", "M-full", "M-dir"))
    )
    layer_b_union = rows["B7"] | rows["B8"] | rows["B9"] | rows["B11"]
    union = layer_a | layer_b_union
    layer_b_only = union - layer_a
    w_ext = {subject for subject in union if corpus(subject) in {"C3", "C5"}}

    anchor_raw = read_jsonl(
        md_paths,
        {"five-iid-historical-anchor"},
    )
    accepted = subjects - fail_set(anchor_raw.values())
    value_witness = {
        str(row["subject_id"])
        for row in md_strict.values()
        if row.get("validation_status") == "fail"
        and row.get("mode") == "eval"
        and not (row.get("parameters") or {})
    }
    crash_witness = {
        str(row["subject_id"])
        for row in md_strict.values()
        if row.get("validation_status") == "fail"
        and bool((row.get("worker_result") or {}).get("errors"))
    }
    context_witness = layer_a - value_witness

    table3 = {}
    for corpus_name in ("C2", "C3", "C5", "Total"):
        scope = (
            subjects
            if corpus_name == "Total"
            else {subject for subject in subjects if corpus(subject) == corpus_name}
        )
        accepted_scope = accepted & scope
        layer_a_scope = accepted_scope & layer_a
        layer_b_scope = accepted_scope & layer_b_only
        union_scope = accepted_scope & union
        table3[corpus_name] = {
            "accepted": len(accepted_scope),
            "layer_a_functional": len(layer_a_scope),
            "layer_b_only": len(layer_b_scope),
            "union_evidence": len(union_scope),
            "union_rate_pct": 100.0 * len(union_scope) / len(accepted_scope),
            "fp32_value": len(accepted_scope & value_witness),
            "dtype_context": len(accepted_scope & context_witness - value_witness),
            "dtype_context_rejection": len(
                (accepted_scope & context_witness - value_witness) & crash_witness
            ),
            "dtype_context_silent_divergence": len(
                (accepted_scope & context_witness - value_witness) - crash_witness
            ),
            "crash_witnessed": len(accepted_scope & crash_witness),
        }

    # Three-way anchor status: rejected (any FAIL), accepted (>=1 PASS and no
    # FAIL), undecidable (all five outcomes INCONCLUSIVE).  Pure re-aggregation
    # of the frozen anchor ledger rows; no new execution.
    anchor_rows_by_subject: dict[str, list[dict]] = defaultdict(list)
    for row in anchor_raw.values():
        anchor_rows_by_subject[str(row["subject_id"])].append(row)
    anchor_status: dict[str, str] = {}
    for subject_id in subjects:
        statuses = {
            str(row.get("validation_status"))
            for row in anchor_rows_by_subject.get(subject_id, [])
        }
        if "fail" in statuses:
            anchor_status[subject_id] = "rejected"
        elif "pass" in statuses:
            anchor_status[subject_id] = "accepted"
        else:
            anchor_status[subject_id] = "undecidable"
    rejected_strict = {s for s, st in anchor_status.items() if st == "rejected"}
    accepted_strict = {s for s, st in anchor_status.items() if st == "accepted"}
    undecidable_strict = {
        s for s, st in anchor_status.items() if st == "undecidable"
    }

    def evidence_breakdown(frame: set[str]) -> dict:
        breakdown = {}
        for corpus_name in ("C2", "C3", "C5", "Total"):
            scope = (
                frame
                if corpus_name == "Total"
                else {s for s in frame if corpus(s) == corpus_name}
            )
            robustness_only_scope = scope & context_witness - value_witness
            breakdown[corpus_name] = {
                "n": len(scope),
                "native_witness": len(scope & value_witness),
                "robustness_only": len(robustness_only_scope),
                # Table 3 (2026-09-06 layout): robustness-only split by failure
                # kind into rejection (candidate raises, reference completes)
                # and silent divergence (both complete, tolerance violated).
                "robustness_only_rejection": len(
                    robustness_only_scope & crash_witness
                ),
                "robustness_only_silent_divergence": len(
                    robustness_only_scope - crash_witness
                ),
                "external_only": len(scope & layer_b_only),
                "union_evidence": len(scope & union),
                "union_rate_pct": (
                    100.0 * len(scope & union) / len(scope) if scope else 0.0
                ),
                "crash_witnessed": len(scope & crash_witness),
            }
        return breakdown

    anchor_panel = {
        "status_counts": {
            "rejected": len(rejected_strict),
            "accepted": len(accepted_strict),
            "undecidable": len(undecidable_strict),
        },
        "status_by_corpus": {
            "rejected": by_corpus(rejected_strict),
            "accepted": by_corpus(accepted_strict),
            "undecidable": by_corpus(undecidable_strict),
        },
        "accepted": evidence_breakdown(accepted_strict),
        "undecidable": evidence_breakdown(undecidable_strict),
    }

    # Actual legacy protocol panel (B1 with its native oracle, on the corpora
    # it executed).  Legacy acceptance semantics: no FAIL.  The strict variant
    # (>=1 PASS and no FAIL) is reported alongside.
    legacy_anchor_rows = strategy_rows(g, "five-iid-historical-anchor")
    legacy_covered = {str(row["subject_id"]) for row in legacy_anchor_rows}
    legacy_rejected = fail_set(legacy_anchor_rows)
    legacy_non_rejected = legacy_covered - legacy_rejected
    legacy_rows_by_subject: dict[str, list[dict]] = defaultdict(list)
    for row in legacy_anchor_rows:
        legacy_rows_by_subject[str(row["subject_id"])].append(row)
    legacy_accepted_strict = {
        subject_id
        for subject_id, subject_rows in legacy_rows_by_subject.items()
        if not any(
            row.get("validation_status") == "fail" for row in subject_rows
        )
        and any(row.get("validation_status") == "pass" for row in subject_rows)
    }
    legacy_panel = {
        "covered": len(legacy_covered),
        "rejected": len(legacy_rejected),
        "non_rejected": len(legacy_non_rejected),
        "non_rejected_with_evidence": len(legacy_non_rejected & union),
        "non_rejected_evidence_rate_pct": (
            100.0 * len(legacy_non_rejected & union) / len(legacy_non_rejected)
        ),
        "accepted_strict": len(legacy_accepted_strict),
        "accepted_strict_with_evidence": len(legacy_accepted_strict & union),
        "accepted_strict_evidence_rate_pct": (
            100.0 * len(legacy_accepted_strict & union)
            / len(legacy_accepted_strict)
        ),
    }

    records = {
        name: row_record(name, detected, w_ext) for name, detected in rows.items()
    }
    comparisons = {
        name: {
            "task_signflip_p_vs_mfull": task_signflip_p(
                rows["M-full"], detected, w_ext
            )
        }
        for name, detected in rows.items()
        if name != "M-full"
    }

    # Dtype-8 exact prefix cost and latency.
    mctx_rows = strategy_rows(md, "dtype-mode-config")
    dtype_rows = [
        row
        for row in mctx_rows
        if row.get("mode") == "eval" and "dtype" in (row.get("parameters") or {})
    ]
    dtype_times, dtype_wall_ms = cumulative_detection(dtype_rows, contracts)
    records["Dtype-8"].update(
        {
            "total_wall_h": dtype_wall_ms / 3.6e6,
            "gpu_s_per_witness": dtype_wall_ms / 1000.0 / len(rows["Dtype-8"]),
            "gpu_h_per_1k": dtype_wall_ms / 3.6e6 / len(subjects) * 1000.0,
            "ttfc_median_s": sorted(dtype_times.values())[
                len(dtype_times) // 2
            ],
            "detected_at_80s": sum(value <= 80.0 for value in dtype_times.values()),
        }
    )

    # Strict-contract operational cost and latency for the audit-tier rows.
    # Wall time is the frozen ledger's in-contract spend plus each repair's
    # spend up to that row's first in-contract FAIL; TTFC walks the planned
    # order through both repairs so a subject decided only after the budget was
    # restored carries its true cumulative latency.
    def streak_wall_through_first_fail_h(display: str) -> float:
        total_ms = 0.0
        for subject_rows in streak_rows_by_subject(streak_dir, display).values():
            for row in sorted(subject_rows, key=lambda r: int(r["source_order"])):
                total_ms += float(row.get("parent_wall_ms") or 0.0)
                if row.get("validation_status") == "fail":
                    break
        return total_ms / 3.6e6

    def audit_tier_latency(strategy_name: str, display: str) -> dict:
        merged: dict[str, list[dict]] = defaultdict(list)
        for subject_id, values in repair_rows_by_subject(
            args.repair_campaign.resolve(), display
        ).items():
            merged[subject_id].extend(values)
        for subject_id, values in streak_rows_by_subject(streak_dir, display).items():
            merged[subject_id].extend(values)
        times, _ = cumulative_detection(
            strategy_rows(md, strategy_name), contracts, merged
        )
        ordered = sorted(times.values())
        return {
            "ttfc_median_s": ordered[len(ordered) // 2],
            "detected_at_80s": sum(value <= 80.0 for value in ordered),
            "decided_subjects": len(ordered),
        }

    repair_summary = read_json(args.repair_summary.resolve())
    strict_cost = {
        "M-full": {
            "wall_h": sum(
                repair_summary["lanes"][lane]["strategies"]["mutakernel-full"][
                    "strict_stop_wall_h"
                ]
                for lane in ("mfull-wave1", "mfull-wave2", "mfull-wave3")
            )
            + streak_wall_through_first_fail_h("M-full"),
            "detections": len(rows["M-full"]),
            "subjects": 838,
            **audit_tier_latency("mutakernel-full", "M-full"),
        },
        "M-dir": {
            "wall_h": sum(
                repair_summary["lanes"][lane]["strategies"][
                    "mutakernel-directed"
                ]["strict_stop_wall_h"]
                for lane in ("mdir-wave1", "mdir-wave2", "mdir-wave3")
            )
            + streak_wall_through_first_fail_h("M-dir"),
            "detections": len(rows["M-dir"]),
            "subjects": 838,
            **audit_tier_latency("mutakernel-directed", "M-dir"),
        },
        "M-legacy": {
            "wall_h": sum(
                repair_summary["lanes"][lane]["strategies"]["mutakernel-full"][
                    "strict_stop_wall_h"
                ]
                for lane in ("mlegacy-wave1", "mlegacy-wave2")
            ),
            "detections": len(rows["M-legacy"]),
            "subjects": 668,
        },
    }
    for value in strict_cost.values():
        value["gpu_s_per_witness"] = (
            value["wall_h"] * 3600.0 / value["detections"]
        )
        value["gpu_h_per_1k"] = (
            value["wall_h"] / value["subjects"] * 1000.0
        )

    lodo = repair_summary["lanes"]["lodo"]["strategies"]
    table10 = {
        "minus_value": {
            "strict_detected": 609,
            "any_envelope_detected": 609,
            "undecidable": 0,
            "loss": [0, 0],
        },
        "minus_dtype": {
            "strict_detected": lodo["mutakernel-lodo-minus-dtype"][
                "repaired_in_contract_detected"
            ],
            "any_envelope_detected": 576,
            "undecidable": lodo["mutakernel-lodo-minus-dtype"][
                "remaining_undecidable"
            ],
            "loss": [336, 340],
        },
        "minus_train": {
            "strict_detected": 607,
            "any_envelope_detected": 607,
            "undecidable": 0,
            "loss": [2, 2],
        },
        "minus_repeat": {
            "strict_detected": lodo["mutakernel-lodo-minus-repeat"][
                "repaired_in_contract_detected"
            ],
            "any_envelope_detected": 607,
            "undecidable": 0,
            "loss": [3, 3],
        },
        "minus_config": {
            "strict_detected": lodo["mutakernel-lodo-minus-config"][
                "repaired_in_contract_detected"
            ],
            "any_envelope_detected": 607,
            "undecidable": 0,
            "loss": [7, 7],
        },
    }

    # Supplementary re-analyses (schema 4.3); repairs enter the audit-tier
    # horizon curves exactly as they enter audit_tier_latency above.
    repairs_by_display: dict[str, dict[str, list[dict]]] = {}
    for strategy_name, display in (
        ("mutakernel-full", "M-full"),
        ("mutakernel-directed", "M-dir"),
    ):
        merged_rows: dict[str, list[dict]] = defaultdict(list)
        for subject_id, values in repair_rows_by_subject(
            args.repair_campaign.resolve(), display
        ).items():
            merged_rows[subject_id].extend(values)
        for subject_id, values in streak_rows_by_subject(streak_dir, display).items():
            merged_rows[subject_id].extend(values)
        repairs_by_display[display] = merged_rows
    instrument1_dir = args.instrument1_dir.resolve()
    e1_root = args.e1_root.resolve()
    kernelbench_root = args.kernelbench_root.resolve()
    probe_ledger_dirs = sorted(
        (data / "c1_unpacked").glob("lane_c1ctx_shard*")
    )
    supplement = compute_supplement(
        md=md,
        md_strict=md_strict,
        contracts=contracts,
        subjects=subjects,
        rows=rows,
        accepted_strict=accepted_strict,
        rejected_strict=rejected_strict,
        value_witness=value_witness,
        crash_witness=crash_witness,
        layer_a=layer_a,
        legacy_covered=legacy_covered,
        anchor_rows=anchor_raw,
        strategy_rows=strategy_rows,
        cumulative_detection=cumulative_detection,
        repairs_by_display=repairs_by_display,
        strict_cost=strict_cost,
        probe_ledger_dirs=probe_ledger_dirs,
        task_of=task,
        corpus_of=corpus,
        kernelbench_root=kernelbench_root,
        e1_root=e1_root,
        sampling_csv=instrument1_dir / "抽样清单_instrument1.csv",
        labels_csv=instrument1_dir / "标注表_A.csv",
        seed=SEED,
        rounds=BOOTSTRAP_ROUNDS,
    )
    supplement_source_files = [
        e1_root / "original_controls.json",
        e1_root / "baseline_observations.jsonl",
        instrument1_dir / "抽样清单_instrument1.csv",
        instrument1_dir / "标注表_A.csv",
        Path(__file__).resolve().parent / "fse_v4_supplement.py",
        *(directory / "observations.jsonl" for directory in probe_ledger_dirs),
        *(
            path
            for level in (1, 2, 3)
            for path in (kernelbench_root / f"level{level}").glob("*.py")
        ),
    ]

    port_source_files = [
        path
        for directories in port_dirs.values()
        for directory in directories
        for path in directory.glob("*_summary.json")
    ]
    b11_source_files = [
        path
        for directory in (
            data / "b11_w15/wave15/lane_p_b11",
            data / "cardc/e3_campaign/wave2/lane_p2_b11",
            p3 / "lane_p3_b11",
        )
        for path in directory.glob("*/b11_result.json")
    ]
    repair_source_files = [
        args.repair_campaign.resolve() / "campaign_index.json",
        *args.repair_campaign.resolve().glob("**/source_test_map.json"),
        *args.repair_campaign.resolve().glob("results/**/observations.jsonl"),
        streak_dir / "campaign_index.json",
        *streak_dir.glob("**/source_test_map.json"),
        *streak_dir.glob("results/**/observations.jsonl"),
    ]
    rq4_source_files = [
        PROJECT_ROOT / "_final_outputs/e1_blueprint_batch1.json",
        PROJECT_ROOT / "_final_outputs/e1_a1_crossfit_closure.json",
        fetched / "b/c1ctx_analysis.json",
        fetched / "b/c1host_attribution.json",
        fetched / "b/purity_replay_summary.json",
    ]
    sources = sorted(
        {
            path.resolve()
            for path in (
                md_paths
                + g_paths
                + manifests
                + [args.repair_summary.resolve(), Path(__file__).resolve()]
                + port_source_files
                + b11_source_files
                + repair_source_files
                + rq4_source_files
                + supplement_source_files
            )
            if path.is_file()
        }
    )
    result = {
        "schema_version": "4.5",
        "contracts": "src.experiments.contract.assert_case_in_contract",
        "repairs": {
            "censoring_suffix": {
                "campaign": str(args.repair_campaign.resolve()),
                "restores": (
                    "stop at the first in-contract FAIL rather than the first "
                    "raw FAIL"
                ),
            },
            "timeout_streak_budget": {
                "campaign": str(streak_dir),
                "restores": (
                    "a row with no FAIL executes its full planned in-contract "
                    "budget; the per-case 180 s timeout is unchanged"
                ),
                "new_detections": {
                    display: sorted(detected)
                    for display, detected in sorted(streak_sets.items())
                },
            },
        },
        "subjects": len(subjects),
        "layers": {
            "A_functional": {
                "subjects": len(layer_a),
                "by_corpus": by_corpus(layer_a),
            },
            "B_only": {
                "subjects": len(layer_b_only),
                "by_corpus": by_corpus(layer_b_only),
            },
            "union": {"subjects": len(union), "by_corpus": by_corpus(union)},
            "W_ext": {"subjects": len(w_ext), "by_corpus": by_corpus(w_ext)},
        },
        "table3": table3,
        "anchor_panel": anchor_panel,
        "legacy_panel": legacy_panel,
        "rows": records,
        "comparisons": comparisons,
        "strict_cost": strict_cost,
        "table9_augmented": {
            "killed": 539,
            "witnessed_survivors": 68,
            "falsified_primary": 7,
            "falsified_followup": 2,
            "proven_non_equivalent": 616,
            "misses": 77,
            "miss_rate_pct": 12.5,
            "unresolved": 450,
            "mechanisms": {
                "value_activation": 70,
                "tolerance_absorption": 5,
                "precision_masking": 2,
            },
        },
        "table10": table10,
        "supplement": supplement,
        "source_files": [
            {"path": str(path), "sha256": sha256_file(path)} for path in sources
        ],
    }
    result["result_sha256"] = stable_json_sha256(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=1),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "result_sha256": result["result_sha256"],
                "layers": result["layers"],
                "dtype8": result["rows"]["Dtype-8"],
                "mfull_mdir_p": result["comparisons"]["M-dir"],
                "table10": table10,
                "anchor_panel": anchor_panel,
                "legacy_panel": legacy_panel,
                "supplement_summary": {
                    "witness_composition": {
                        key: supplement["witness_composition"][key]
                        for key in (
                            "rejection_classes",
                            "robustness_only_silent_divergence",
                            "native_tolerance_robust",
                            "native_tolerance_and_tf32_robust_core",
                            "native_legacy_pass_on_observed_case",
                        )
                    },
                    "two_case_projection": supplement["two_case_projection"],
                    "fixed_horizon": {
                        k: v["detected_by"] for k, v in supplement["fixed_horizon"].items()
                    },
                    "anchor_oracle_flip": supplement["anchor_oracle_flip"],
                    "cost_decomposition": {
                        k: {
                            "total_per_1k": round(v["total_per_1k"], 1),
                            "fixed_per_1k": round(v["fixed_per_1k"], 1),
                            "marginal_per_1k": round(v["marginal_per_1k"], 1),
                            "gpu_s_per_witness": round(v["gpu_s_per_witness"], 1),
                        }
                        for k, v in supplement["cost_decomposition"].items()
                    },
                    "undecided_causes": supplement["undecided_causes"],
                    "probe_source_duplicates": supplement["probe_source_duplicates"],
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
