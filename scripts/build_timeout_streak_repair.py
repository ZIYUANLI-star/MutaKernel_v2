#!/usr/bin/env python3
"""Build a frozen repair campaign for cases the timeout-streak breaker skipped.

Table 2 of the manuscript states that a budget-matched subject with no FAIL
always executes its full planned budget.  The production runner additionally
carried ``timeout_streak_limit=5``: after five consecutive 180 s parent
timeouts on one (subject, strategy) pair it recorded every remaining planned
case as INCONCLUSIVE with zero wall time and never executed it.  That guard was
added mid-campaign and is not part of the frozen protocol, so rows it touched
violate the documented budget semantics.

Selection rule (outcome-independent, applied to every affected row):

1. the (subject, strategy) row has no FAIL observation at all;
2. at least one planned case was recorded with ``worker_result.phase ==
   "timeout_streak"`` and zero parent wall time; and
3. only such never-executed cases that ``assert_case_in_contract`` accepts are
   selected.

The emitted artifacts are ordinary schema-v1 in-contract plans, identical in
shape to ``build_minimal_repair_campaign.py`` output, so the unchanged
production runner executes them at the same 180 s per-case timeout with the
breaker disabled.  Original ledgers and plans are never modified.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_minimal_repair_campaign import (  # noqa: E402
    REPAIR_SCOPE,
    assemble_plan,
    canonical_case,
    case_is_in_contract,
    case_signature,
    read_json,
    rehash_manifest,
    rehash_subject,
)
from src.experiments.manifest import sha256_file, stable_json_sha256  # noqa: E402
from src.experiments.protocol import write_plan_once  # noqa: E402
from src.experiments.strategy import StrategySpec, TestCaseSpec  # noqa: E402

CAMPAIGN_ID = "timeout-streak-repair-20260827"
SELECTION_RULE = (
    "row has no FAIL; case was recorded by the runner's timeout-streak breaker "
    "(worker phase timeout_streak, zero parent wall) and therefore never "
    "executed; only cases accepted by assert_case_in_contract are selected"
)


@dataclass(frozen=True)
class Lane:
    name: str
    source_plan: Path
    subject_manifest: Path
    ledgers: tuple[Path, ...]
    strategy_names: tuple[str, ...]


def observation_rank(row: Mapping[str, object]) -> int:
    """Prefer a real verdict, then a real execution, then a skipped record."""
    if row.get("validation_status") == "fail":
        return 3
    if float(row.get("parent_wall_ms") or 0.0) > 0.0:
        return 2
    return 1


def load_rows(paths: Iterable[Path], strategy_names: set[str]) -> dict:
    rows: dict[tuple[str, str], dict] = {}
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("strategy_name") not in strategy_names:
                    continue
                key = (str(row["subject_id"]), str(row["test_id"]))
                previous = rows.get(key)
                if previous is None or observation_rank(row) > observation_rank(previous):
                    rows[key] = row
    return rows


def was_streak_skipped(row: Mapping[str, object]) -> bool:
    worker = row.get("worker_result")
    phase = worker.get("phase") if isinstance(worker, Mapping) else None
    return phase == "timeout_streak" and float(row.get("parent_wall_ms") or 0.0) == 0.0


def lane_groups(lane: Lane) -> tuple[list[dict], dict]:
    source_plan = read_json(lane.source_plan)
    source_manifest = read_json(lane.subject_manifest)
    subject_by_id = {
        str(subject["subject_id"]): subject for subject in source_manifest["subjects"]
    }
    strategy_names = set(lane.strategy_names)
    observed = load_rows(lane.ledgers, strategy_names)

    schedule_by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for entry in source_plan["schedule"]:
        strategy_name = str(entry["strategy_name"])
        if strategy_name in strategy_names:
            schedule_by_pair[(str(entry["subject_id"]), strategy_name)].append(entry)
    for entries in schedule_by_pair.values():
        entries.sort(key=lambda value: int(value["order"]))

    observed_by_pair: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for (subject_id, test_id), row in observed.items():
        observed_by_pair[(subject_id, str(row["strategy_name"]))][test_id] = row

    groups: dict[tuple[str, str], dict] = {}
    audit = {
        "lane": lane.name,
        "source_plan": str(lane.source_plan),
        "source_plan_sha256": source_plan["plan_sha256"],
        "subject_manifest": str(lane.subject_manifest),
        "ledgers": [str(path) for path in lane.ledgers],
        "selection_rule": SELECTION_RULE,
        "strategy_counts": {},
        "subjects": {},
    }
    for pair, source_entries in schedule_by_pair.items():
        subject_id, strategy_name = pair
        subject = subject_by_id[subject_id]
        pair_observed = observed_by_pair.get(pair, {})
        if not pair_observed:
            continue
        if any(
            row.get("validation_status") == "fail" for row in pair_observed.values()
        ):
            continue
        skipped_ids = {
            test_id
            for test_id, row in pair_observed.items()
            if was_streak_skipped(row)
        }
        if not skipped_ids:
            continue
        missing = [
            entry
            for entry in source_entries
            if str(entry["test_id"]) in skipped_ids
            and case_is_in_contract(entry, subject["contract"])
        ]
        if not missing:
            continue

        timed_out = sum(
            1
            for row in pair_observed.values()
            if float(row.get("parent_wall_ms") or 0.0) > 0.0
            and row.get("validation_status") == "inconclusive"
        )
        signature = case_signature(missing)
        candidate_runs = sum(
            int((entry.get("parameters") or {})["repeat_count"])
            if entry.get("mode") == "repeated"
            else 1
            for entry in missing
        )
        group_key = (strategy_name, str(candidate_runs))
        group = groups.setdefault(
            group_key,
            {
                "strategy_name": strategy_name,
                "candidate_runs": candidate_runs,
                "signatures_by_subject": {},
                "source_entries_by_subject": {},
            },
        )
        group["signatures_by_subject"][subject_id] = signature
        group["source_entries_by_subject"][subject_id] = missing
        audit["subjects"][subject_id + "::" + strategy_name] = {
            "planned_cases": len(source_entries),
            "ledger_cases": len(pair_observed),
            "executed_timeouts": timed_out,
            "streak_skipped_cases": len(skipped_ids),
            "streak_skipped_in_contract": len(missing),
            "source_test_ids": [entry["test_id"] for entry in missing],
        }

    output_groups: list[dict] = []
    for (strategy_name, _), group in sorted(groups.items()):
        subject_ids = sorted(group["source_entries_by_subject"])
        aggregate_signature = stable_json_sha256(
            {
                subject_id: group["signatures_by_subject"][subject_id]
                for subject_id in subject_ids
            }
        )
        output_groups.append(
            {**group, "signature": aggregate_signature, "subject_ids": subject_ids}
        )

    for strategy_name in lane.strategy_names:
        selected = [
            group for group in output_groups if group["strategy_name"] == strategy_name
        ]
        audit["strategy_counts"][strategy_name] = {
            "groups": len(selected),
            "subjects": sum(len(group["subject_ids"]) for group in selected),
            "cases": sum(
                len(group["subject_ids"]) * group["candidate_runs"]
                for group in selected
            ),
        }
    return output_groups, audit


def write_lane(lane: Lane, output_root: Path) -> dict:
    groups, audit = lane_groups(lane)
    source_plan = read_json(lane.source_plan)
    source_manifest = read_json(lane.subject_manifest)
    source_subjects = {
        str(subject["subject_id"]): subject for subject in source_manifest["subjects"]
    }
    lane_dir = output_root / lane.name
    lane_dir.mkdir(parents=True, exist_ok=True)
    group_records = []

    for index, group in enumerate(groups):
        group_id = f"{index:02d}-{group['strategy_name']}-{group['signature'][:10]}"
        group_dir = lane_dir / group_id
        group_dir.mkdir(parents=True, exist_ok=False)
        subjects = [
            rehash_subject(copy.deepcopy(source_subjects[subject_id]))
            for subject_id in group["subject_ids"]
        ]
        manifest = rehash_manifest(source_manifest, subjects)
        manifest_path = group_dir / "subject_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=1),
            encoding="utf-8",
        )

        candidate_runs = int(group["candidate_runs"])
        strategy = StrategySpec(
            name=f"repair-{lane.name}-{index:02d}",
            version="1",
            parameters={
                "comparison_role": "timeout_streak_budget_repair",
                "source_plan_sha256": source_plan["plan_sha256"],
                "source_strategy": group["strategy_name"],
                "source_case_signature_sha256": group["signature"],
                "repair_scope": "streak_skipped_in_contract_cases_only",
                "per_case_timeout_s": 180.0,
                "timeout_streak_limit": None,
                "budget_matched": False,
                "candidate_runs": candidate_runs,
            },
        )
        cases_by_subject: dict[str, list[TestCaseSpec]] = {}
        source_mapping = {}
        for subject_id in group["subject_ids"]:
            specs = []
            source_entries = group["source_entries_by_subject"][subject_id]
            for entry in source_entries:
                case = canonical_case(entry)
                specs.append(
                    TestCaseSpec(
                        subject_id=subject_id,
                        strategy=strategy,
                        policy=case["policy"],
                        seed=case["seed"],
                        mode=case["mode"],
                        scope=REPAIR_SCOPE,
                        parameters=case["parameters"],
                        replicate=case["replicate"],
                    )
                )
            cases_by_subject[subject_id] = specs
            source_mapping[subject_id] = [
                {
                    "source_test_id": entry["test_id"],
                    "source_order": entry["order"],
                    "repair_case": spec.to_dict(),
                }
                for entry, spec in zip(source_entries, specs)
            ]

        matrix_ref = {
            "kind": "timeout-streak-budget-repair",
            "lane": lane.name,
            "source_plan": str(lane.source_plan),
            "source_plan_sha256": source_plan["plan_sha256"],
            "source_strategy": group["strategy_name"],
            "source_case_signature_sha256": group["signature"],
            "selection_rule": SELECTION_RULE,
            "envelope_note": (
                "per-case timeout unchanged at 180 s; only the mid-campaign "
                "timeout-streak breaker is disabled, restoring the documented "
                "full-budget semantics for rows with no FAIL"
            ),
        }
        plan_path = group_dir / "repair_plan.json"
        matrix_ref_path = Path(str(plan_path) + ".matrix_ref.json")
        plan = assemble_plan(
            manifest=manifest,
            manifest_path=manifest_path,
            strategy=strategy,
            candidate_runs=candidate_runs,
            cases_by_subject=cases_by_subject,
            matrix_ref=matrix_ref,
            matrix_ref_path=matrix_ref_path,
            matrix_id=f"timeout-repair-{lane.name}-{index:02d}-v1",
        )
        write_plan_once(plan_path, plan)
        source_map_path = group_dir / "source_test_map.json"
        source_map_path.write_text(
            json.dumps(source_mapping, ensure_ascii=False, sort_keys=True, indent=1),
            encoding="utf-8",
        )
        group_records.append(
            {
                "group_id": group_id,
                "source_strategy": group["strategy_name"],
                "subjects": len(group["subject_ids"]),
                "candidate_runs_per_subject": candidate_runs,
                "test_cases": plan["test_case_count"],
                "manifest": str(manifest_path.relative_to(output_root)),
                "manifest_sha256": manifest["manifest_sha256"],
                "plan": str(plan_path.relative_to(output_root)),
                "plan_sha256": plan["plan_sha256"],
                "matrix_ref": str(matrix_ref_path.relative_to(output_root)),
                "source_test_map": str(source_map_path.relative_to(output_root)),
                "source_test_map_file_sha256": sha256_file(source_map_path),
            }
        )

    audit_path = lane_dir / "selection_audit.json"
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, sort_keys=True, indent=1),
        encoding="utf-8",
    )
    return {
        "lane": lane.name,
        "source_plan": str(lane.source_plan),
        "source_plan_sha256": source_plan["plan_sha256"],
        "selection_audit": str(audit_path.relative_to(output_root)),
        "selection_audit_file_sha256": sha256_file(audit_path),
        "groups": group_records,
        "subjects": sum(record["subjects"] for record in group_records),
        "test_cases": sum(record["test_cases"] for record in group_records),
    }


def campaign_lanes(root: Path, fetched: Path) -> list[Lane]:
    cardc = root / "cardc" / "e3_campaign"
    wave1_manifest = cardc / "wave1_subject_manifest_v2.json"
    wave1_m_plan = cardc / "wave1_lane_m_plan_v2.json"
    lane_m_ledger = (
        root / "root" / "mk_v2_runs" / "e3_campaign" / "lane_m_run" / "observations.jsonl"
    )
    lane_d_ledger = cardc / "wave15" / "lane_d_run" / "observations.jsonl"
    shared = dict(
        source_plan=wave1_m_plan,
        subject_manifest=wave1_manifest,
        ledgers=(lane_m_ledger,),
    )
    return [
        Lane(name="streak-b1u", strategy_names=("five-iid-historical-anchor",), **shared),
        Lane(name="streak-b3", strategy_names=("iid-compute-matched",), **shared),
        Lane(name="streak-b4", strategy_names=("diversified-value",), **shared),
        Lane(name="streak-b5", strategy_names=("boundary-values",), **shared),
        Lane(name="streak-mctx", strategy_names=("dtype-mode-config",), **shared),
        Lane(name="streak-mfull", strategy_names=("mutakernel-full",), **shared),
        Lane(
            name="streak-mdir",
            source_plan=fetched / "c" / "lane_d_plan.json",
            subject_manifest=wave1_manifest,
            ledgers=(lane_d_ledger,),
            strategy_names=("mutakernel-directed",),
        ),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--fetched-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    lane_records = []
    for lane in campaign_lanes(args.data_root.resolve(), args.fetched_root.resolve()):
        print(f"[timeout-repair] selecting {lane.name}", flush=True)
        record = write_lane(lane, output_dir)
        if record["test_cases"]:
            lane_records.append(record)
        else:
            print(f"[timeout-repair]   {lane.name}: no affected rows", flush=True)
    index = {
        "schema_version": "1.0",
        "campaign_id": CAMPAIGN_ID,
        "selection_rule": SELECTION_RULE,
        "envelope_note": (
            "per-case timeout unchanged at 180 s; the mid-campaign "
            "timeout_streak_limit=5 guard is disabled so rows with no FAIL "
            "execute their full planned in-contract budget as documented"
        ),
        "data_root": str(args.data_root.resolve()),
        "fetched_root": str(args.fetched_root.resolve()),
        "lanes": lane_records,
        "subjects": sum(record["subjects"] for record in lane_records),
        "test_cases": sum(record["test_cases"] for record in lane_records),
    }
    index["campaign_sha256"] = stable_json_sha256(index)
    (output_dir / "campaign_index.json").write_text(
        json.dumps(index, ensure_ascii=False, sort_keys=True, indent=1),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output_dir),
                "campaign_sha256": index["campaign_sha256"],
                "subjects": index["subjects"],
                "test_cases": index["test_cases"],
                "lanes": {
                    record["lane"]: {
                        "source_strategy": record["groups"][0]["source_strategy"],
                        "subjects": record["subjects"],
                        "test_cases": record["test_cases"],
                    }
                    for record in lane_records
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
