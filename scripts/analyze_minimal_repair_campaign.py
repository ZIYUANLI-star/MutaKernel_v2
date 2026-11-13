#!/usr/bin/env python3
"""Merge minimal repair observations with frozen ledgers and report strict results."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_minimal_repair_campaign import (  # noqa: E402
    campaign_lanes,
    case_is_in_contract,
    load_reconciled_rows,
    read_json,
)
from src.experiments.manifest import sha256_file, stable_json_sha256  # noqa: E402


def relative_path(root: Path, value: str) -> Path:
    return root / value.replace("\\", "/")


def read_observations(path: Path) -> dict[str, dict]:
    rows = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            test_id = str(row["test_id"])
            previous = rows.get(test_id)
            if previous is None or (
                previous.get("validation_status") != "fail"
                and row.get("validation_status") == "fail"
            ):
                rows[test_id] = row
    return rows


def repair_rows(campaign_dir: Path, lane_record: dict) -> tuple[list[dict], dict]:
    merged = []
    audit = {
        "expected": 0,
        "observed": 0,
        "status": Counter(),
        "wall_ms": 0.0,
        "groups": {},
    }
    for group in lane_record["groups"]:
        source_map = read_json(relative_path(campaign_dir, group["source_test_map"]))
        repair_to_source = {}
        for subject_id, mappings in source_map.items():
            for mapping in mappings:
                repair_case = mapping["repair_case"]
                repair_to_source[str(repair_case["test_id"])] = {
                    "subject_id": subject_id,
                    "source_test_id": str(mapping["source_test_id"]),
                    "source_order": int(mapping["source_order"]),
                }
        observations_path = (
            campaign_dir
            / "results"
            / lane_record["lane"]
            / group["group_id"]
            / "observations.jsonl"
        )
        if not observations_path.is_file():
            raise FileNotFoundError(observations_path)
        observations = read_observations(observations_path)
        expected_ids = set(repair_to_source)
        observed_ids = set(observations)
        if expected_ids != observed_ids:
            raise RuntimeError(
                f"{group['group_id']}: missing={len(expected_ids-observed_ids)} "
                f"unexpected={len(observed_ids-expected_ids)}"
            )
        group_status = Counter()
        for test_id, row in observations.items():
            source = repair_to_source[test_id]
            enriched = {
                **row,
                **source,
                "repair_test_id": test_id,
                "group_id": group["group_id"],
            }
            merged.append(enriched)
            status = str(row["validation_status"])
            group_status[status] += 1
            audit["status"][status] += 1
            audit["wall_ms"] += float(row.get("parent_wall_ms") or 0.0)
        audit["expected"] += len(expected_ids)
        audit["observed"] += len(observed_ids)
        audit["groups"][group["group_id"]] = dict(group_status)
    audit["status"] = dict(audit["status"])
    return merged, audit


def baseline_summary(lane, repair: list[dict]) -> dict:
    manifest = read_json(lane.subject_manifest)
    contracts = {
        str(subject["subject_id"]): subject["contract"]
        for subject in manifest["subjects"]
    }
    strategy_names = set(lane.strategy_names)
    baseline = load_reconciled_rows(lane.ledgers, strategy_names)

    observed_by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for (subject_id, _), row in baseline.items():
        observed_by_pair[(subject_id, str(row["strategy_name"]))].append(row)
    repair_by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in repair:
        # A lane contains one source strategy per repair group.
        source_strategy = next(
            strategy
            for strategy in lane.strategy_names
            if strategy in row["group_id"]
            or len(lane.strategy_names) == 1
        )
        repair_by_pair[(str(row["subject_id"]), source_strategy)].append(row)

    strategies = {}
    for strategy_name in lane.strategy_names:
        baseline_detected = set()
        repaired_detected = set()
        raw_ext_only = set()
        resolved_no_detection = set()
        remaining_undecidable = set()
        strict_wall_ms = 0.0
        repair_wall_until_fail_ms = 0.0
        status = Counter()
        pairs = {
            pair
            for pair in set(observed_by_pair) | set(repair_by_pair)
            if pair[1] == strategy_name
        }
        for subject_id, _ in pairs:
            contract = contracts[subject_id]
            observed = observed_by_pair.get((subject_id, strategy_name), [])
            in_contract_observed = [
                row for row in observed if case_is_in_contract(row, contract)
            ]
            for row in in_contract_observed:
                strict_wall_ms += float(row.get("parent_wall_ms") or 0.0)
            if any(
                row.get("validation_status") == "fail"
                for row in in_contract_observed
            ):
                baseline_detected.add(subject_id)
                repaired_detected.add(subject_id)
            elif any(row.get("validation_status") == "fail" for row in observed):
                raw_ext_only.add(subject_id)

            suffix = sorted(
                repair_by_pair.get((subject_id, strategy_name), []),
                key=lambda row: int(row["source_order"]),
            )
            suffix_has_fail = any(
                row.get("validation_status") == "fail" for row in suffix
            )
            suffix_has_inconclusive = any(
                row.get("validation_status") == "inconclusive" for row in suffix
            )
            if subject_id in raw_ext_only:
                if suffix_has_fail:
                    repaired_detected.add(subject_id)
                elif suffix_has_inconclusive:
                    remaining_undecidable.add(subject_id)
                else:
                    # An empty suffix means the original ledger had already
                    # completed every planned in-contract case.
                    resolved_no_detection.add(subject_id)
            for row in suffix:
                status[str(row["validation_status"])] += 1
                repair_wall_until_fail_ms += float(row.get("parent_wall_ms") or 0.0)
                if row.get("validation_status") == "fail":
                    repaired_detected.add(subject_id)
                    break

        strategies[strategy_name] = {
            "baseline_in_contract_detected": len(baseline_detected),
            "raw_extended_only_rows": len(raw_ext_only),
            "repaired_in_contract_detected": len(repaired_detected),
            "new_detections": len(repaired_detected - baseline_detected),
            "resolved_no_detection": len(resolved_no_detection),
            "remaining_undecidable": len(remaining_undecidable),
            "repair_status_through_first_fail": dict(status),
            "baseline_in_contract_wall_h": strict_wall_ms / 3.6e6,
            "repair_wall_through_first_fail_h": (
                repair_wall_until_fail_ms / 3.6e6
            ),
            "strict_stop_wall_h": (
                strict_wall_ms + repair_wall_until_fail_ms
            )
            / 3.6e6,
        }
    return strategies


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--fetched-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--blocking-retry", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    campaign_dir = args.campaign_dir.resolve()
    index = read_json(campaign_dir / "campaign_index.json")
    payload = dict(index)
    campaign_sha = payload.pop("campaign_sha256")
    if stable_json_sha256(payload) != campaign_sha:
        raise RuntimeError("campaign index digest mismatch")

    lane_by_name = {
        lane.name: lane
        for lane in campaign_lanes(
            args.data_root.resolve(), args.fetched_root.resolve()
        )
    }
    result = {
        "schema_version": "1.0",
        "campaign_sha256": campaign_sha,
        "lanes": {},
    }
    for lane_record in index["lanes"]:
        lane_name = lane_record["lane"]
        repair, repair_audit = repair_rows(campaign_dir, lane_record)
        result["lanes"][lane_name] = {
            "repair": repair_audit,
            "strategies": baseline_summary(lane_by_name[lane_name], repair),
        }
    if args.blocking_retry:
        retry_rows = read_observations(args.blocking_retry.resolve())
        result["cuda_launch_blocking_retry"] = {
            "path": str(args.blocking_retry.resolve()),
            "file_sha256": sha256_file(args.blocking_retry.resolve()),
            "cases": len(retry_rows),
            "subjects": len(
                {str(row["subject_id"]) for row in retry_rows.values()}
            ),
            "statuses": dict(
                Counter(
                    str(row["validation_status"]) for row in retry_rows.values()
                )
            ),
            "reason_prefixes": dict(
                Counter(
                    str((row.get("worker_result") or {}).get("reason", "")).split(
                        "\n", 1
                    )[0]
                    for row in retry_rows.values()
                )
            ),
        }
    result["result_sha256"] = stable_json_sha256(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=1),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
