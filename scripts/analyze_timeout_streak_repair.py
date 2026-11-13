#!/usr/bin/env python3
"""Merge the timeout-streak repair observations with the frozen ledgers.

For every affected (subject, strategy) row this reports the baseline verdict
state, what the repaired cases produced, and whether the row gains a strict
in-contract detection once the documented full-budget semantics are restored.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_minimal_repair_campaign import read_observations, relative_path  # noqa: E402
from build_minimal_repair_campaign import case_is_in_contract, read_json  # noqa: E402
from build_timeout_streak_repair import campaign_lanes, load_rows  # noqa: E402
from src.experiments.manifest import stable_json_sha256  # noqa: E402


def repair_rows(campaign_dir: Path, lane_record: dict) -> tuple[list[dict], dict]:
    merged: list[dict] = []
    audit = {"expected": 0, "observed": 0, "status": Counter(), "wall_ms": 0.0}
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
                f"{group['group_id']}: missing={len(expected_ids - observed_ids)} "
                f"unexpected={len(observed_ids - expected_ids)}"
            )
        for test_id, row in observations.items():
            merged.append(
                {
                    **row,
                    **repair_to_source[test_id],
                    "repair_test_id": test_id,
                    "group_id": group["group_id"],
                    "source_strategy": group["source_strategy"],
                }
            )
            audit["status"][str(row["validation_status"])] += 1
            audit["wall_ms"] += float(row.get("parent_wall_ms") or 0.0)
        audit["expected"] += len(expected_ids)
        audit["observed"] += len(observed_ids)
    audit["status"] = dict(audit["status"])
    return merged, audit


def lane_summary(lane, repair: list[dict]) -> dict:
    manifest = read_json(lane.subject_manifest)
    contracts = {
        str(subject["subject_id"]): subject["contract"]
        for subject in manifest["subjects"]
    }
    strategy_name = lane.strategy_names[0]
    baseline = load_rows(lane.ledgers, {strategy_name})

    subjects = sorted({str(row["subject_id"]) for row in repair})
    result = {"strategy": strategy_name, "subjects": {}}
    for subject_id in subjects:
        contract = contracts[subject_id]
        observed = [
            row for (sid, _), row in baseline.items() if sid == subject_id
        ]
        in_contract = [row for row in observed if case_is_in_contract(row, contract)]
        baseline_detected = any(
            row.get("validation_status") == "fail" for row in in_contract
        )
        suffix = sorted(
            (row for row in repair if str(row["subject_id"]) == subject_id),
            key=lambda row: int(row["source_order"]),
        )
        first_fail = next(
            (row for row in suffix if row.get("validation_status") == "fail"), None
        )
        wall_to_first_fail = 0.0
        for row in suffix:
            wall_to_first_fail += float(row.get("parent_wall_ms") or 0.0)
            if row.get("validation_status") == "fail":
                break
        result["subjects"][subject_id] = {
            "baseline_in_contract_detected": baseline_detected,
            "repair_cases": len(suffix),
            "repair_status": dict(
                Counter(str(row["validation_status"]) for row in suffix)
            ),
            "repaired_detects": bool(first_fail) or baseline_detected,
            "new_detection": bool(first_fail) and not baseline_detected,
            "first_fail_case": (
                {
                    "source_order": first_fail["source_order"],
                    "policy": first_fail.get("policy"),
                    "mode": first_fail.get("mode"),
                    "parameters": first_fail.get("parameters"),
                    "reason": str(
                        (first_fail.get("worker_result") or {}).get("reason", "")
                    )[:200],
                    "errors": [
                        str(e)[:200]
                        for e in ((first_fail.get("worker_result") or {}).get("errors") or [])
                    ][:2],
                }
                if first_fail
                else None
            ),
            "repair_wall_h_through_first_fail": wall_to_first_fail / 3.6e6,
            "repair_wall_h_total": sum(
                float(row.get("parent_wall_ms") or 0.0) for row in suffix
            )
            / 3.6e6,
        }
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--fetched-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
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
        "campaign_id": index["campaign_id"],
        "campaign_sha256": campaign_sha,
        "envelope_note": index["envelope_note"],
        "selection_rule": index["selection_rule"],
        "lanes": {},
    }
    new_detections: dict[str, list[str]] = {}
    for lane_record in index["lanes"]:
        lane_name = lane_record["lane"]
        repair, repair_audit = repair_rows(campaign_dir, lane_record)
        summary = lane_summary(lane_by_name[lane_name], repair)
        result["lanes"][lane_name] = {"repair": repair_audit, **summary}
        gained = [
            subject
            for subject, value in summary["subjects"].items()
            if value["new_detection"]
        ]
        if gained:
            new_detections[summary["strategy"]] = gained
    result["new_detections_by_strategy"] = new_detections
    result["result_sha256"] = stable_json_sha256(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=1),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
