#!/usr/bin/env python3
"""Wave-1.5 lane-plan builder (M-dir / legacy-oracle / LODO / subset manifests).

Design (preregistered in
MutakernelV2/实验/补充实验数据/E3_wave15_补链战役设计_20260805.md):

* All plans are hand-assembled frozen plans in the exact schema of
  ``src.experiments.protocol`` and MUST pass ``validate_frozen_plan`` before
  being written; the tested validator is the single gatekeeper, this builder
  adds no execution semantics of its own.
* ``mdir-plan``    Lane D: one ``mutakernel-directed`` row whose cases vary per
                   subject (frozen map + static fingerprint, 70/30 split).
                   Budget shortfall after dedup is filled deterministically by
                   cycling the frozen general sequence with replicate-derived
                   seeds (rule: general-cycle-derive-seed).
* ``legacy-manifest`` Lane G input: contract variant manifest whose oracle is
                   the flat legacy tolerance (atol=rtol=1e-2, no dtype table);
                   everything else byte-identical.  Metadata records the
                   variant tag.
* ``matrix-plan``  Lane G runs: anchor + mutakernel-full rows (verbatim
                   templates from the frozen matrix) over a subset manifest.
* ``lodo-plan``    Lane L: five leave-one-dimension-out rows, ``--variant
                   full`` (retained-then-replacement, 32 calls) or ``--variant
                   delta`` (replacement cases only).  Replacement rule:
                   retained-cycle-seed-increment (see design doc).
* ``subset-manifest`` reusable subject-subset extraction with re-hashing.

No file in the mk_v2 git worktree is modified: this tool lives out-of-repo
until Lane M releases the environment freeze, then is committed verbatim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

MK_ROOT = Path("/root/mk_v2")
sys.path.insert(0, str(MK_ROOT))

from src.experiments.manifest import sha256_file, stable_json_sha256  # noqa: E402
from src.experiments.protocol import (  # noqa: E402
    PROTOCOL_SCHEMA_VERSION,
    ProtocolError,
    validate_frozen_plan,
    write_plan_once,
)
from src.experiments.strategy import StrategySpec, TestCaseSpec  # noqa: E402
from src.experiments.contract import (  # noqa: E402
    validate_case_parameters,
    validate_contract,
)

EXPERIMENT_SCOPE = "extended_contract"


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _rehash_subject(subject: dict) -> dict:
    subject = dict(subject)
    subject["contract_sha256"] = stable_json_sha256(subject["contract"])
    payload = dict(subject)
    payload.pop("subject_sha256", None)
    subject["subject_sha256"] = stable_json_sha256(payload)
    return subject


def _rehash_manifest(manifest: dict, subjects: list) -> dict:
    manifest = dict(manifest)
    manifest["subjects"] = subjects
    manifest["subject_count"] = len(subjects)
    manifest["subjects_sha256"] = stable_json_sha256(subjects)
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = stable_json_sha256(payload)
    return manifest


def _load_subject_ids(path: Path) -> list:
    ids = [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not ids:
        raise SystemExit(f"subject-id file is empty: {path}")
    if len(ids) != len(set(ids)):
        raise SystemExit(f"subject-id file has duplicates: {path}")
    return ids


def _subset_manifest(manifest: dict, subject_ids: list) -> dict:
    by_id = {s["subject_id"]: s for s in manifest["subjects"]}
    missing = [sid for sid in subject_ids if sid not in by_id]
    if missing:
        raise SystemExit(f"subject ids not in manifest: {missing[:5]} ...")
    subjects = [by_id[sid] for sid in sorted(subject_ids)]
    return _rehash_manifest(manifest, subjects)


def _case_cost(mode: str, parameters: dict) -> int:
    if mode == "repeated":
        return int(parameters["repeat_count"])
    return 1


def _assemble_plan(
    *,
    manifest: dict,
    manifest_path: Path,
    rows: list,
    matrix_ref: dict,
    matrix_id: str,
    out: Path,
) -> dict:
    """rows: list of dicts {spec: StrategySpec, budget_matched, candidate_runs,
    cases_by_subject: {subject_id: [TestCaseSpec, ...]}}

    ``matrix_ref`` is written next to the plan as the lane's matrix descriptor
    so that both matrix digests in the plan point at a real artifact."""

    matrix_ref_path = Path(str(out) + ".matrix_ref.json")
    matrix_ref_path.write_text(
        json.dumps(matrix_ref, ensure_ascii=False, sort_keys=True, indent=1),
        encoding="utf-8",
    )

    subjects = sorted(manifest["subjects"], key=lambda s: s["subject_id"])
    queues = []
    for subject in subjects:
        for row in rows:
            cases = row["cases_by_subject"][subject["subject_id"]]
            queues.append((subject, row, cases))

    schedule = []
    order = 1
    max_len = max(len(q[2]) for q in queues)
    for round_index in range(max_len):
        for subject, row, cases in queues:
            if round_index >= len(cases):
                continue
            entry = cases[round_index].to_dict()
            entry.update(
                {
                    "order": order,
                    "candidate_run_cost": cases[round_index].candidate_run_cost,
                    "budget_matched": row["budget_matched"],
                    "strategy_candidate_run_budget": row["candidate_runs"],
                    "dataset": subject["dataset"],
                    "task_id": subject["task_id"],
                }
            )
            schedule.append(entry)
            order += 1

    strategy_summaries = [
        {
            "strategy_id": row["spec"].strategy_id,
            "name": row["spec"].name,
            "version": row["spec"].version,
            "budget_matched": row["budget_matched"],
            "candidate_runs_per_subject": row["candidate_runs"],
            "parameters": row["spec"].parameters,
        }
        for row in rows
    ]
    payload = {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "matrix_id": matrix_id,
        "experiment_scope": EXPERIMENT_SCOPE,
        "subject_manifest_sha256": manifest["manifest_sha256"],
        "subject_manifest_file_sha256": sha256_file(Path(manifest_path)),
        "strategy_matrix_sha256": stable_json_sha256(matrix_ref),
        "strategy_matrix_file_sha256": sha256_file(matrix_ref_path),
        "candidate_run_budget": 32,
        "subject_count": len(subjects),
        "strategy_count": len(rows),
        "test_case_count": len(schedule),
        "strategies": strategy_summaries,
        "schedule": schedule,
        "schedule_sha256": stable_json_sha256(schedule),
    }
    payload["plan_sha256"] = stable_json_sha256(payload)
    return payload


def _validate_and_write(plan: dict, manifest: dict, out: Path) -> None:
    validate_frozen_plan(plan, manifest)
    write_plan_once(Path(out), plan)
    print(
        json.dumps(
            {
                "written": str(out),
                "plan_sha256": plan["plan_sha256"],
                "subjects": plan["subject_count"],
                "strategies": [s["name"] for s in plan["strategies"]],
                "test_cases": plan["test_case_count"],
            },
            indent=2,
        )
    )


# ---------------------------------------------------------------------------
# mdir-plan (Lane D)
# ---------------------------------------------------------------------------

def cmd_mdir_plan(args):
    from src.mutengine.fingerprint import build_site_fingerprint
    from src.validator.site_directed import (
        DEFAULT_GENERAL_SEQUENCE,
        derive_seed,
        derive_site_directed_plan,
    )

    manifest = _read_json(args.subjects)
    map_bytes = Path(args.map).read_bytes()
    fault_map = json.loads(map_bytes)
    map_sha256 = hashlib.sha256(map_bytes).hexdigest()

    spec = StrategySpec(
        name="mutakernel-directed",
        version="1",
        parameters={
            "comparison_role": "site_directed_method",
            "sampling_family": "site_directed",
            "map_version": fault_map.get("map_version"),
            "map_sha256": map_sha256,
            "directed_fraction": args.directed_fraction,
            "fill_rule": "general-cycle-derive-seed",
            "budget_matched": True,
            "candidate_runs": args.budget,
        },
    )

    artifact_root = Path(args.artifact_root)
    cases_by_subject = {}
    stats = {"directed_total": 0, "general_total": 0, "fill_total": 0}
    for subject in manifest["subjects"]:
        sid = subject["subject_id"]
        source_path = artifact_root / subject["candidate"]["logical_path"].lstrip("/")
        source = source_path.read_text(encoding="utf-8", errors="replace")
        fingerprint = build_site_fingerprint(source, sid)
        derived = derive_site_directed_plan(
            subject_id=sid,
            fingerprint=fingerprint,
            fault_to_stress_map=fault_map,
            budget_candidate_calls=args.budget,
            is_authorized=None,  # extended_contract scope: post-hoc classification
            directed_fraction=args.directed_fraction,
        )
        planned = [
            {
                "policy": c["policy"],
                "mode": c["mode"],
                "parameters": dict(c["parameters"]),
                "seed": c["seed"],
            }
            for c in derived["plan"]
        ]
        stats["directed_total"] += derived["budget"]["directed_calls"]
        stats["general_total"] += derived["budget"]["general_calls"]
        spent = derived["budget"]["planned_calls"]

        # Deterministic budget fill: cycle the frozen general sequence with
        # replicate-derived seeds until the budget is exactly consumed.
        replicate_round = 1
        while spent < args.budget:
            progressed = False
            for template in DEFAULT_GENERAL_SEQUENCE:
                cost = _case_cost(template["mode"], template.get("parameters") or {})
                if spent + cost > args.budget:
                    continue
                planned.append(
                    {
                        "policy": template["policy"],
                        "mode": template["mode"],
                        "parameters": dict(template.get("parameters") or {}),
                        "seed": derive_seed(sid, template, replicate_round),
                    }
                )
                stats["fill_total"] += cost
                spent += cost
                progressed = True
                if spent >= args.budget:
                    break
            if not progressed:
                raise ProtocolError(f"budget fill stalled for subject {sid}")
            replicate_round += 1

        specs = []
        seen = set()
        for case in planned:
            validate_case_parameters(case["parameters"], case["mode"])
            tcs = TestCaseSpec(
                subject_id=sid,
                strategy=spec,
                policy=case["policy"],
                seed=case["seed"],
                mode=case["mode"],
                scope=EXPERIMENT_SCOPE,
                parameters=case["parameters"],
                replicate=0,
            )
            if tcs.test_id in seen:
                raise ProtocolError(f"duplicate mdir test id for subject {sid}")
            seen.add(tcs.test_id)
            specs.append(tcs)
        total_cost = sum(t.candidate_run_cost for t in specs)
        if total_cost != args.budget:
            raise ProtocolError(f"subject {sid} cost {total_cost} != {args.budget}")
        cases_by_subject[sid] = specs

    rows = [
        {
            "spec": spec,
            "budget_matched": True,
            "candidate_runs": args.budget,
            "cases_by_subject": cases_by_subject,
        }
    ]
    matrix_ref = {
        "kind": "wave15-lane-d-mdir",
        "map_sha256": map_sha256,
        "directed_fraction": args.directed_fraction,
        "fill_rule": "general-cycle-derive-seed",
    }
    plan = _assemble_plan(
        manifest=manifest,
        manifest_path=args.subjects,
        rows=rows,
        matrix_ref=matrix_ref,
        matrix_id="wave15-lane-d-mdir-v1",
        out=args.out,
    )
    _validate_and_write(plan, manifest, args.out)
    print(json.dumps({"mdir_stats": stats}, indent=2))


# ---------------------------------------------------------------------------
# legacy-manifest (Lane G input)
# ---------------------------------------------------------------------------

LEGACY_ORACLE = {"atol": 0.01, "rtol": 0.01}


def cmd_legacy_manifest(args):
    manifest = _read_json(args.subjects)
    if args.subject_ids:
        manifest = _subset_manifest(manifest, _load_subject_ids(args.subject_ids))

    subjects = []
    for subject in manifest["subjects"]:
        subject = json.loads(json.dumps(subject))  # deep copy
        contract = subject["contract"]
        contract["oracle"]["atol"] = LEGACY_ORACLE["atol"]
        contract["oracle"]["rtol"] = LEGACY_ORACLE["rtol"]
        contract["oracle"]["dtype_tolerances"] = {}
        normalized = validate_contract(contract)
        if normalized != contract:
            raise SystemExit(
                f"legacy contract for {subject['subject_id']} is not canonical"
            )
        metadata = dict(subject.get("metadata") or {})
        metadata["oracle_variant"] = "legacy-flat-1e-2"
        metadata["oracle_variant_note"] = (
            "wave-1.5 Lane G: flat KernelBench-style tolerance "
            "(atol=rtol=1e-2, no dtype table); all other clauses byte-identical "
            "to the frozen wave-1 contract"
        )
        subject["metadata"] = metadata
        subjects.append(_rehash_subject(subject))

    out_manifest = _rehash_manifest(manifest, subjects)
    out = Path(args.out)
    out.write_text(
        json.dumps(out_manifest, ensure_ascii=False, sort_keys=True, indent=1),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "written": str(out),
                "subjects": out_manifest["subject_count"],
                "manifest_sha256": out_manifest["manifest_sha256"],
            },
            indent=2,
        )
    )


# ---------------------------------------------------------------------------
# matrix-plan (Lane G runs; verbatim rows from the frozen matrix)
# ---------------------------------------------------------------------------

def _rows_from_matrix(matrix: dict, names: list, manifest: dict) -> list:
    rows = []
    for raw in matrix["strategies"]:
        if raw["name"] not in names:
            continue
        spec = StrategySpec(
            name=raw["name"],
            version=raw["version"],
            parameters={
                **dict(raw["parameters"]),
                "budget_matched": raw["budget_matched"],
                "candidate_runs": raw["candidate_runs"],
            },
        )
        cases_by_subject = {}
        for subject in manifest["subjects"]:
            specs = []
            for template in raw["cases"]:
                for seed in template["seeds"]:
                    for replicate in range(template.get("replicates", 1)):
                        specs.append(
                            TestCaseSpec(
                                subject_id=subject["subject_id"],
                                strategy=spec,
                                policy=template["policy"],
                                seed=seed,
                                mode=template["mode"],
                                scope=EXPERIMENT_SCOPE,
                                parameters=template["parameters"],
                                replicate=replicate,
                            )
                        )
            cases_by_subject[subject["subject_id"]] = specs
        rows.append(
            {
                "spec": spec,
                "budget_matched": raw["budget_matched"],
                "candidate_runs": raw["candidate_runs"],
                "cases_by_subject": cases_by_subject,
            }
        )
    missing = set(names) - {r["spec"].name for r in rows}
    if missing:
        raise SystemExit(f"matrix is missing strategies: {sorted(missing)}")
    return rows


def cmd_matrix_plan(args):
    manifest = _read_json(args.subjects)
    matrix = _read_json(args.matrix)
    rows = _rows_from_matrix(matrix, args.strategy_names, manifest)
    plan = _assemble_plan(
        manifest=manifest,
        manifest_path=args.subjects,
        rows=rows,
        matrix_ref={
            "kind": "wave15-matrix-subset",
            "source_matrix_id": matrix.get("matrix_id"),
            "strategies": args.strategy_names,
        },
        matrix_id=args.matrix_id,
        out=args.out,
    )
    _validate_and_write(plan, manifest, args.out)


# ---------------------------------------------------------------------------
# lodo-plan (Lane L)
# ---------------------------------------------------------------------------

# Dimension partition of the 31 mutakernel-full cases (declared order kept).
LODO_DIMENSIONS = {
    "value": lambda c: (
        c["mode"] == "eval" and not c["parameters"]
    ),
    "dtype": lambda c: (
        c["mode"] == "eval" and "dtype" in c["parameters"]
    ),
    "train": lambda c: c["mode"] == "train",
    "repeat": lambda c: c["mode"] == "repeated",
    "config": lambda c: (
        c["mode"] == "config"
        or (c["mode"] == "eval" and "layout" in c["parameters"])
    ),
}


def _mfull_flat_cases(matrix: dict) -> list:
    for raw in matrix["strategies"]:
        if raw["name"] == "mutakernel-full":
            flat = []
            for template in raw["cases"]:
                for seed in template["seeds"]:
                    flat.append(
                        {
                            "policy": template["policy"],
                            "seed": seed,
                            "mode": template["mode"],
                            "parameters": dict(template["parameters"]),
                        }
                    )
            return flat
    raise SystemExit("matrix has no mutakernel-full row")


def _lodo_rows_templates(matrix: dict) -> dict:
    """Return {dimension: {retained: [...], replacements: [...]}} templates."""
    flat = _mfull_flat_cases(matrix)
    # sanity: partition must be exact
    for case in flat:
        hits = [d for d, pred in LODO_DIMENSIONS.items() if pred(case)]
        if len(hits) != 1:
            raise SystemExit(f"case does not partition uniquely: {case} -> {hits}")

    out = {}
    for dim in LODO_DIMENSIONS:
        retained = [c for c in flat if not LODO_DIMENSIONS[dim](c)]
        removed = [c for c in flat if LODO_DIMENSIONS[dim](c)]
        removed_cost = sum(_case_cost(c["mode"], c["parameters"]) for c in removed)

        replacements = []
        budget = removed_cost
        cycle = 1
        while budget > 0:
            progressed = False
            for case in retained:
                cost = _case_cost(case["mode"], case["parameters"])
                if cost > budget:
                    continue
                replacements.append(
                    {
                        "policy": case["policy"],
                        "seed": 100000 * cycle + case["seed"],
                        "mode": case["mode"],
                        "parameters": dict(case["parameters"]),
                    }
                )
                budget -= cost
                progressed = True
                if budget == 0:
                    break
            if not progressed:
                raise SystemExit(f"lodo fill stalled for dimension {dim}")
            cycle += 1
        out[dim] = {
            "retained": retained,
            "replacements": replacements,
            "removed_cost": removed_cost,
        }
    return out


def cmd_lodo_plan(args):
    manifest = _read_json(args.subjects)
    matrix = _read_json(args.matrix)
    templates = _lodo_rows_templates(matrix)

    rows = []
    for dim in sorted(templates):
        info = templates[dim]
        if args.variant == "full":
            case_list = info["retained"] + info["replacements"]
            candidate_runs = 32
            budget_matched = True
        else:
            case_list = info["replacements"]
            candidate_runs = info["removed_cost"]
            budget_matched = False
        spec = StrategySpec(
            name=f"mutakernel-lodo-minus-{dim}",
            version="1",
            parameters={
                "comparison_role": "leave_one_dimension_out",
                "sampling_family": "mutakernel_stress",
                "removed_dimension": dim,
                "variant": args.variant,
                "reallocation_rule": "retained-cycle-seed-increment",
                "budget_matched": budget_matched,
                "candidate_runs": candidate_runs,
            },
        )
        cases_by_subject = {}
        for subject in manifest["subjects"]:
            specs = []
            seen = set()
            for case in case_list:
                validate_case_parameters(case["parameters"], case["mode"])
                tcs = TestCaseSpec(
                    subject_id=subject["subject_id"],
                    strategy=spec,
                    policy=case["policy"],
                    seed=case["seed"],
                    mode=case["mode"],
                    scope=EXPERIMENT_SCOPE,
                    parameters=case["parameters"],
                    replicate=0,
                )
                if tcs.test_id in seen:
                    raise SystemExit(f"lodo duplicate case {dim} {case}")
                seen.add(tcs.test_id)
                specs.append(tcs)
            total = sum(t.candidate_run_cost for t in specs)
            if total != candidate_runs:
                raise SystemExit(f"lodo {dim} cost {total} != {candidate_runs}")
            cases_by_subject[subject["subject_id"]] = specs
        rows.append(
            {
                "spec": spec,
                "budget_matched": budget_matched,
                "candidate_runs": candidate_runs,
                "cases_by_subject": cases_by_subject,
            }
        )

    plan = _assemble_plan(
        manifest=manifest,
        manifest_path=args.subjects,
        rows=rows,
        matrix_ref={
            "kind": "wave15-lane-l-lodo",
            "variant": args.variant,
            "source_matrix_id": matrix.get("matrix_id"),
            "reallocation_rule": "retained-cycle-seed-increment",
        },
        matrix_id=f"wave15-lane-l-lodo-{args.variant}-v1",
        out=args.out,
    )
    _validate_and_write(plan, manifest, args.out)


# ---------------------------------------------------------------------------
# subset-manifest
# ---------------------------------------------------------------------------

def cmd_subset_manifest(args):
    manifest = _read_json(args.subjects)
    subset = _subset_manifest(manifest, _load_subject_ids(args.subject_ids))
    Path(args.out).write_text(
        json.dumps(subset, ensure_ascii=False, sort_keys=True, indent=1),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "written": str(args.out),
                "subjects": subset["subject_count"],
                "manifest_sha256": subset["manifest_sha256"],
            },
            indent=2,
        )
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("mdir-plan")
    p.add_argument("--subjects", required=True, type=Path)
    p.add_argument("--map", required=True, type=Path)
    p.add_argument("--artifact-root", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--budget", type=int, default=32)
    p.add_argument("--directed-fraction", type=float, default=0.7)
    p.set_defaults(func=cmd_mdir_plan)

    p = sub.add_parser("legacy-manifest")
    p.add_argument("--subjects", required=True, type=Path)
    p.add_argument("--subject-ids", type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.set_defaults(func=cmd_legacy_manifest)

    p = sub.add_parser("matrix-plan")
    p.add_argument("--subjects", required=True, type=Path)
    p.add_argument("--matrix", required=True, type=Path)
    p.add_argument("--strategy-names", nargs="+", required=True)
    p.add_argument("--matrix-id", required=True)
    p.add_argument("--out", required=True, type=Path)
    p.set_defaults(func=cmd_matrix_plan)

    p = sub.add_parser("lodo-plan")
    p.add_argument("--subjects", required=True, type=Path)
    p.add_argument("--matrix", required=True, type=Path)
    p.add_argument("--variant", choices=["full", "delta"], required=True)
    p.add_argument("--out", required=True, type=Path)
    p.set_defaults(func=cmd_lodo_plan)

    p = sub.add_parser("subset-manifest")
    p.add_argument("--subjects", required=True, type=Path)
    p.add_argument("--subject-ids", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.set_defaults(func=cmd_subset_manifest)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
