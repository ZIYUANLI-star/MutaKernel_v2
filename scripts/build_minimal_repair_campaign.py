#!/usr/bin/env python3
"""Build a frozen, in-contract-only repair campaign for censored FSE rows.

The production campaigns stopped a subject/strategy row after its first raw
FAIL.  When that FAIL was outside the signed task contract, later in-contract
cases were not executed.  This builder:

1. reads the original frozen plans and append-only ledgers;
2. identifies rows with an out-of-contract FAIL and no in-contract FAIL;
3. selects only planned in-contract cases that have no ledger observation;
4. groups subjects with byte-identical missing case sequences; and
5. emits ordinary schema-v1 manifests/plans that the unchanged production
   runner can execute with early stopping disabled.

Original ledgers and plans are never modified.  Every repair case records its
source test_id in ``campaign_index.json``.
"""

from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import json
import sys
import types
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Contract/plan validation is structural and does not execute tensor code.  The
# artifact builder is intentionally usable on a CPU-only analysis host where
# PyTorch is absent; production execution revalidates the same plans with the
# real PyTorch installation on the GPU node.
try:  # pragma: no cover - exercised only on analysis hosts without PyTorch.
    import torch as _torch  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    sys.modules["torch"] = types.ModuleType("torch")

from src.experiments.contract import (  # noqa: E402
    ContractError,
    assert_case_in_contract,
    validate_contract,
)
from src.experiments.manifest import (  # noqa: E402
    sha256_file,
    stable_json_sha256,
)
from src.experiments.protocol import (  # noqa: E402
    PROTOCOL_SCHEMA_VERSION,
    validate_frozen_plan,
    write_plan_once,
)
from src.experiments.strategy import StrategySpec, TestCaseSpec  # noqa: E402


REPAIR_SCOPE = "in_contract"
LEGACY_TOLERANCE = 1e-2


@dataclass(frozen=True)
class Lane:
    name: str
    source_plan: Path
    subject_manifest: Path
    ledgers: tuple[Path, ...]
    strategy_names: tuple[str, ...]
    legacy_oracle: bool = False


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def canonical_case(entry: Mapping[str, object]) -> dict:
    return {
        "policy": str(entry["policy"]),
        "seed": entry["seed"],
        "mode": str(entry["mode"]),
        "parameters": dict(entry.get("parameters") or {}),
        "replicate": int(entry.get("replicate", 0)),
    }


def case_signature(entries: Sequence[Mapping[str, object]]) -> str:
    return stable_json_sha256([canonical_case(entry) for entry in entries])


def case_is_in_contract(entry: Mapping[str, object], contract: Mapping[str, object]) -> bool:
    try:
        assert_case_in_contract(
            {
                "policy": entry["policy"],
                "mode": entry["mode"],
                "parameters": entry.get("parameters") or {},
            },
            contract,
        )
    except ContractError:
        return False
    return True


def rehash_subject(subject: dict) -> dict:
    subject = copy.deepcopy(subject)
    subject["contract_sha256"] = stable_json_sha256(subject["contract"])
    payload = dict(subject)
    payload.pop("subject_sha256", None)
    subject["subject_sha256"] = stable_json_sha256(payload)
    return subject


def rehash_manifest(manifest: dict, subjects: list[dict]) -> dict:
    result = copy.deepcopy(manifest)
    result["subjects"] = subjects
    result["subject_count"] = len(subjects)
    result["subjects_sha256"] = stable_json_sha256(subjects)
    payload = dict(result)
    payload.pop("manifest_sha256", None)
    result["manifest_sha256"] = stable_json_sha256(payload)
    return result


def apply_legacy_oracle(subject: dict) -> dict:
    result = copy.deepcopy(subject)
    contract = result["contract"]
    contract["oracle"]["atol"] = LEGACY_TOLERANCE
    contract["oracle"]["rtol"] = LEGACY_TOLERANCE
    contract["oracle"]["dtype_tolerances"] = {}
    result["contract"] = validate_contract(contract)
    metadata = dict(result.get("metadata") or {})
    metadata["oracle_variant"] = "legacy-flat-1e-2"
    metadata["oracle_variant_note"] = (
        "minimal repair: flat legacy tolerance (atol=rtol=1e-2, no dtype "
        "table); every non-oracle contract clause is unchanged"
    )
    result["metadata"] = metadata
    return rehash_subject(result)


def load_reconciled_rows(paths: Iterable[Path], strategy_names: set[str]) -> dict:
    """Return {(subject_id, test_id): row}; FAIL wins over duplicate non-FAIL."""
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
                if previous is None or (
                    previous.get("validation_status") != "fail"
                    and row.get("validation_status") == "fail"
                ):
                    rows[key] = row
    return rows


def assemble_plan(
    *,
    manifest: dict,
    manifest_path: Path,
    strategy: StrategySpec,
    candidate_runs: int,
    cases_by_subject: Mapping[str, Sequence[TestCaseSpec]],
    matrix_ref: dict,
    matrix_ref_path: Path,
    matrix_id: str,
) -> dict:
    subjects = sorted(manifest["subjects"], key=lambda value: value["subject_id"])
    schedule: list[dict] = []
    order = 1
    max_len = max(len(cases_by_subject[subject["subject_id"]]) for subject in subjects)
    for round_index in range(max_len):
        for subject in subjects:
            cases = cases_by_subject[subject["subject_id"]]
            if round_index >= len(cases):
                continue
            case = cases[round_index]
            entry = case.to_dict()
            entry.update(
                {
                    "order": order,
                    "candidate_run_cost": case.candidate_run_cost,
                    "budget_matched": False,
                    "strategy_candidate_run_budget": candidate_runs,
                    "dataset": subject["dataset"],
                    "task_id": subject["task_id"],
                }
            )
            schedule.append(entry)
            order += 1

    matrix_ref_path.write_text(
        json.dumps(matrix_ref, ensure_ascii=False, sort_keys=True, indent=1),
        encoding="utf-8",
    )
    payload = {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "matrix_id": matrix_id,
        "experiment_scope": REPAIR_SCOPE,
        "subject_manifest_sha256": manifest["manifest_sha256"],
        "subject_manifest_file_sha256": sha256_file(manifest_path),
        "strategy_matrix_sha256": stable_json_sha256(matrix_ref),
        "strategy_matrix_file_sha256": sha256_file(matrix_ref_path),
        "candidate_run_budget": 32,
        "subject_count": len(subjects),
        "strategy_count": 1,
        "test_case_count": len(schedule),
        "strategies": [
            {
                "strategy_id": strategy.strategy_id,
                "name": strategy.name,
                "version": strategy.version,
                "budget_matched": False,
                "candidate_runs_per_subject": candidate_runs,
                "parameters": strategy.parameters,
            }
        ],
        "schedule": schedule,
        "schedule_sha256": stable_json_sha256(schedule),
    }
    payload["plan_sha256"] = stable_json_sha256(payload)
    validate_frozen_plan(payload, manifest)
    return payload


def lane_groups(lane: Lane) -> tuple[list[dict], dict]:
    source_plan = read_json(lane.source_plan)
    source_manifest = read_json(lane.subject_manifest)
    subject_by_id = {
        str(subject["subject_id"]): subject for subject in source_manifest["subjects"]
    }
    strategy_names = set(lane.strategy_names)
    observed = load_reconciled_rows(lane.ledgers, strategy_names)

    schedule_by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for entry in source_plan["schedule"]:
        strategy_name = str(entry["strategy_name"])
        if strategy_name in strategy_names:
            schedule_by_pair[(str(entry["subject_id"]), strategy_name)].append(entry)
    for entries in schedule_by_pair.values():
        entries.sort(key=lambda value: int(value["order"]))

    observed_by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for (subject_id, _), row in observed.items():
        observed_by_pair[(subject_id, str(row["strategy_name"]))].append(row)

    groups: dict[tuple[str, str], dict] = {}
    audit = {
        "lane": lane.name,
        "source_plan": str(lane.source_plan),
        "source_plan_sha256": source_plan["plan_sha256"],
        "subject_manifest": str(lane.subject_manifest),
        "ledgers": [str(path) for path in lane.ledgers],
        "strategy_counts": {},
        "subjects": {},
    }
    for pair, source_entries in schedule_by_pair.items():
        subject_id, strategy_name = pair
        subject = subject_by_id[subject_id]
        pair_observed = observed_by_pair.get(pair, [])
        fail_rows = [
            row for row in pair_observed if row.get("validation_status") == "fail"
        ]
        if not fail_rows:
            continue
        has_in_contract_fail = any(
            case_is_in_contract(row, subject["contract"]) for row in fail_rows
        )
        if has_in_contract_fail:
            continue
        executed_test_ids = {str(row["test_id"]) for row in pair_observed}
        missing = [
            entry
            for entry in source_entries
            if str(entry["test_id"]) not in executed_test_ids
            and case_is_in_contract(entry, subject["contract"])
        ]
        if not missing:
            continue

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
            "raw_fail_count": len(fail_rows),
            "executed_cases": len(pair_observed),
            "missing_in_contract_cases": len(missing),
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
            {
                **group,
                "signature": aggregate_signature,
                "subject_ids": subject_ids,
            }
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
            copy.deepcopy(source_subjects[subject_id])
            for subject_id in group["subject_ids"]
        ]
        if lane.legacy_oracle:
            subjects = [apply_legacy_oracle(subject) for subject in subjects]
        else:
            subjects = [rehash_subject(subject) for subject in subjects]
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
                "comparison_role": "minimal_censoring_suffix_repair",
                "source_plan_sha256": source_plan["plan_sha256"],
                "source_strategy": group["strategy_name"],
                "source_case_signature_sha256": group["signature"],
                "repair_scope": "missing_in_contract_cases_only",
                "legacy_oracle": lane.legacy_oracle,
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
            "kind": "minimal-censoring-suffix-repair",
            "lane": lane.name,
            "source_plan": str(lane.source_plan),
            "source_plan_sha256": source_plan["plan_sha256"],
            "source_strategy": group["strategy_name"],
            "source_case_signature_sha256": group["signature"],
            "selection_rule": (
                "raw FAIL observed; no in-contract FAIL observed; execute only "
                "planned in-contract cases with no source-ledger observation"
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
            matrix_id=f"minimal-repair-{lane.name}-{index:02d}-v1",
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
        "legacy_oracle": lane.legacy_oracle,
        "source_plan": str(lane.source_plan),
        "source_plan_sha256": source_plan["plan_sha256"],
        "selection_audit": str(audit_path.relative_to(output_root)),
        "selection_audit_file_sha256": sha256_file(audit_path),
        "groups": group_records,
        "subjects": sum(record["subjects"] for record in group_records),
        "test_cases": sum(record["test_cases"] for record in group_records),
    }


def expand_paths(patterns: Sequence[str]) -> tuple[Path, ...]:
    paths = []
    for pattern in patterns:
        matched = [Path(path) for path in glob.glob(pattern)]
        if not matched and Path(pattern).is_file():
            matched = [Path(pattern)]
        if not matched:
            raise FileNotFoundError(pattern)
        paths.extend(matched)
    return tuple(sorted(set(path.resolve() for path in paths)))


def campaign_lanes(root: Path, fetched: Path) -> list[Lane]:
    cardc = root / "cardc" / "e3_campaign"
    w23 = root / "w23"
    wave1_manifest = cardc / "wave1_subject_manifest_v2.json"
    wave2_manifest = cardc / "wave2_subject_manifest.json"
    wave3_manifest = fetched / "b" / "wave3_subject_manifest.json"
    wave1_m_plan = cardc / "wave1_lane_m_plan_v2.json"
    wave2_m_plan = cardc / "wave2_lane_m_plan.json"
    wave3_m_plan = fetched / "b" / "wave3_lane_m_plan.json"
    return [
        Lane(
            name="lodo",
            source_plan=fetched / "c" / "lane_lb_plan.json",
            subject_manifest=fetched / "c" / "lane_lb_manifest.json",
            ledgers=(cardc / "lane_lb_final_merged.jsonl",),
            strategy_names=(
                "mutakernel-lodo-minus-dtype",
                "mutakernel-lodo-minus-repeat",
                "mutakernel-lodo-minus-config",
            ),
        ),
        Lane(
            name="mfull-wave1",
            source_plan=wave1_m_plan,
            subject_manifest=wave1_manifest,
            ledgers=(
                root
                / "root"
                / "mk_v2_runs"
                / "e3_campaign"
                / "lane_m_run"
                / "observations.jsonl",
            ),
            strategy_names=("mutakernel-full",),
        ),
        Lane(
            name="mfull-wave2",
            source_plan=wave2_m_plan,
            subject_manifest=wave2_manifest,
            ledgers=(w23 / "wave2" / "lane_m2_run" / "observations.jsonl",),
            strategy_names=("mutakernel-full",),
        ),
        Lane(
            name="mfull-wave3",
            source_plan=wave3_m_plan,
            subject_manifest=wave3_manifest,
            ledgers=(w23 / "wave3" / "lane_m3_run" / "observations.jsonl",),
            strategy_names=("mutakernel-full",),
        ),
        Lane(
            name="mdir-wave1",
            source_plan=fetched / "c" / "lane_d_plan.json",
            subject_manifest=wave1_manifest,
            ledgers=(cardc / "wave15" / "lane_d_run" / "observations.jsonl",),
            strategy_names=("mutakernel-directed",),
        ),
        Lane(
            name="mdir-wave2",
            source_plan=cardc / "wave2_mdir_plan.json",
            subject_manifest=wave2_manifest,
            ledgers=(w23 / "wave2" / "lane_d2_run" / "observations.jsonl",),
            strategy_names=("mutakernel-directed",),
        ),
        Lane(
            name="mdir-wave3",
            source_plan=fetched / "b" / "wave3_mdir_plan.json",
            subject_manifest=wave3_manifest,
            ledgers=(w23 / "wave3" / "lane_d3_run" / "observations.jsonl",),
            strategy_names=("mutakernel-directed",),
        ),
        Lane(
            name="mlegacy-wave1",
            source_plan=wave1_m_plan,
            subject_manifest=wave1_manifest,
            ledgers=expand_paths(
                [
                    str(
                        root
                        / "root"
                        / "mk_v2_runs"
                        / "e3_campaign"
                        / "wave15"
                        / "lane_g_run_shard*"
                        / "observations.jsonl"
                    )
                ]
            ),
            strategy_names=("mutakernel-full",),
            legacy_oracle=True,
        ),
        Lane(
            name="mlegacy-wave2",
            source_plan=wave2_m_plan,
            subject_manifest=wave2_manifest,
            ledgers=expand_paths(
                [
                    str(
                        w23
                        / "wave2"
                        / "lane_g2_run_shard*"
                        / "observations.jsonl"
                    )
                ]
            ),
            strategy_names=("mutakernel-full",),
            legacy_oracle=True,
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
        print(f"[repair] selecting {lane.name}", flush=True)
        lane_records.append(write_lane(lane, output_dir))
    index = {
        "schema_version": "1.0",
        "campaign_id": "minimal-censoring-repair-20260826",
        "selection_rule": (
            "raw FAIL observed; no in-contract FAIL observed; execute only "
            "missing planned cases accepted by assert_case_in_contract"
        ),
        "data_root": str(args.data_root.resolve()),
        "fetched_root": str(args.fetched_root.resolve()),
        "lanes": lane_records,
        "subjects": sum(record["subjects"] for record in lane_records),
        "test_cases": sum(record["test_cases"] for record in lane_records),
    }
    index["campaign_sha256"] = stable_json_sha256(index)
    index_path = output_dir / "campaign_index.json"
    index_path.write_text(
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
                        "subjects": record["subjects"],
                        "test_cases": record["test_cases"],
                        "groups": len(record["groups"]),
                    }
                    for record in lane_records
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
