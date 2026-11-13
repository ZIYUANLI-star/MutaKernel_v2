#!/usr/bin/env python3
"""Execute a frozen minimal-censoring repair campaign on one GPU node.

The campaign directory is produced by ``build_minimal_repair_campaign.py``.
Every group is an ordinary schema-v1 in-contract plan.  This orchestrator
performs a full hash/artifact preflight, runs a one-case smoke test, then
executes groups with bounded process-level concurrency.  It is idempotent:
the production runner resumes each group by stable repair test_id.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(
    os.environ.get(
        "MUTAKERNEL_REPO",
        "/root/mk_v2"
        if Path("/root/mk_v2").is_dir()
        else str(Path(__file__).resolve().parents[1]),
    )
)
sys.path.insert(0, str(PROJECT_ROOT))

from src.experiments.manifest import sha256_file, stable_json_sha256
from src.experiments.protocol import validate_frozen_plan


def log(message: str, path: Path) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {message}"
    print(line, flush=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def relative_path(campaign_dir: Path, value: str) -> Path:
    return campaign_dir / value.replace("\\", "/")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifact(root: Path, artifact: dict) -> None:
    path = root / str(artifact["logical_path"]).lstrip("/")
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(artifact["size_bytes"]):
        raise RuntimeError(f"artifact size mismatch: {path}")
    if sha256_path(path) != artifact["sha256"]:
        raise RuntimeError(f"artifact sha256 mismatch: {path}")


def preflight(
    campaign_dir: Path,
    artifact_root: Path,
    repo: Path,
    environment: Path,
    log_path: Path,
) -> list[dict]:
    index = read_json(campaign_dir / "campaign_index.json")
    payload = dict(index)
    expected_campaign_sha = payload.pop("campaign_sha256")
    if stable_json_sha256(payload) != expected_campaign_sha:
        raise RuntimeError("campaign_index.json digest mismatch")
    if not environment.is_file():
        raise FileNotFoundError(environment)
    if not (repo / "scripts" / "run_fse_experiment.py").is_file():
        raise FileNotFoundError(repo / "scripts" / "run_fse_experiment.py")

    groups = []
    verified_subjects = set()
    for lane in index["lanes"]:
        for group in lane["groups"]:
            plan_path = relative_path(campaign_dir, group["plan"])
            manifest_path = relative_path(campaign_dir, group["manifest"])
            matrix_ref_path = relative_path(campaign_dir, group["matrix_ref"])
            source_map_path = relative_path(campaign_dir, group["source_test_map"])
            for path in (plan_path, manifest_path, matrix_ref_path, source_map_path):
                if not path.is_file():
                    raise FileNotFoundError(path)
            if sha256_file(source_map_path) != group["source_test_map_file_sha256"]:
                raise RuntimeError(f"source map digest mismatch: {source_map_path}")
            plan = read_json(plan_path)
            manifest = read_json(manifest_path)
            if plan["plan_sha256"] != group["plan_sha256"]:
                raise RuntimeError(f"plan digest differs from campaign index: {plan_path}")
            if manifest["manifest_sha256"] != group["manifest_sha256"]:
                raise RuntimeError(
                    f"manifest digest differs from campaign index: {manifest_path}"
                )
            validate_frozen_plan(plan, manifest)
            for subject in manifest["subjects"]:
                subject_id = str(subject["subject_id"])
                if subject_id not in verified_subjects:
                    verify_artifact(artifact_root, subject["candidate"])
                    verify_artifact(artifact_root, subject["reference"])
                    verified_subjects.add(subject_id)
            groups.append(
                {
                    **group,
                    "lane": lane["lane"],
                    "plan_path": plan_path,
                    "manifest_path": manifest_path,
                }
            )
    log(
        f"preflight ok: {len(groups)} groups, {len(verified_subjects)} unique "
        f"subjects, {index['test_cases']} repair cases",
        log_path,
    )
    return groups


def runner_command(
    *,
    python: str,
    repo: Path,
    environment: Path,
    artifact_root: Path,
    campaign_dir: Path,
    group: dict,
    output_dir: Path,
    max_tests: int | None = None,
) -> list[str]:
    group_token = f"{group['lane']}-{group['group_id']}"
    run_id = f"minimal-repair-20260826-{group_token}"
    if max_tests is not None:
        run_id += "-smoke"
    command = [
        python,
        "-u",
        str(repo / "scripts" / "run_fse_experiment.py"),
        "--plan",
        str(group["plan_path"]),
        "--subjects",
        str(group["manifest_path"]),
        "--environment",
        str(environment),
        "--artifact-root",
        str(artifact_root),
        "--output-dir",
        str(output_dir),
        "--run-id",
        run_id,
        "--device",
        "cuda",
        "--timeout",
        "180.0",
    ]
    if max_tests is not None:
        command.extend(["--max-tests", str(max_tests)])
    return command


def prepare_output(output_dir: Path, shared_extensions: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    link = output_dir / "torch_extensions"
    if not link.exists():
        link.symlink_to(shared_extensions, target_is_directory=True)


def run_smoke(
    *,
    args: argparse.Namespace,
    group: dict,
    campaign_dir: Path,
    log_path: Path,
) -> None:
    smoke_dir = campaign_dir / "smoke" / f"{group['lane']}-{group['group_id']}"
    prepare_output(smoke_dir, args.shared_extensions)
    command = runner_command(
        python=args.python,
        repo=args.repo,
        environment=args.environment,
        artifact_root=args.artifact_root,
        campaign_dir=campaign_dir,
        group=group,
        output_dir=smoke_dir,
        max_tests=1,
    )
    log(f"smoke start: {group['lane']}/{group['group_id']}", log_path)
    result = subprocess.run(
        command,
        cwd=args.repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PATH": "/usr/local/cuda/bin:" + os.environ.get("PATH", "")},
    )
    (smoke_dir / "smoke.log").write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(
            f"smoke failed ({result.returncode}):\n{result.stdout[-3000:]}"
        )
    observations = smoke_dir / "observations.jsonl"
    if not observations.is_file() or observations.stat().st_size == 0:
        raise RuntimeError("smoke produced no observation")
    log("smoke passed", log_path)


def execute_groups(
    *,
    args: argparse.Namespace,
    groups: list[dict],
    campaign_dir: Path,
    log_path: Path,
) -> None:
    pending = list(groups)
    running: dict[str, tuple[subprocess.Popen, object, Path]] = {}
    results_root = campaign_dir / "results"
    results_root.mkdir(exist_ok=True)
    while pending or running:
        while pending and len(running) < args.max_parallel:
            group = pending.pop(0)
            token = f"{group['lane']}-{group['group_id']}"
            output_dir = results_root / group["lane"] / group["group_id"]
            prepare_output(output_dir, args.shared_extensions)
            command = runner_command(
                python=args.python,
                repo=args.repo,
                environment=args.environment,
                artifact_root=args.artifact_root,
                campaign_dir=campaign_dir,
                group=group,
                output_dir=output_dir,
            )
            group_log = output_dir / "runner.log"
            handle = group_log.open("a", encoding="utf-8")
            process = subprocess.Popen(
                command,
                cwd=args.repo,
                stdout=handle,
                stderr=subprocess.STDOUT,
                env={
                    **os.environ,
                    "PATH": "/usr/local/cuda/bin:" + os.environ.get("PATH", ""),
                },
            )
            running[token] = (process, handle, output_dir)
            log(
                f"started {token}: {group['subjects']} subjects, "
                f"{group['test_cases']} cases",
                log_path,
            )
        time.sleep(15)
        for token, (process, handle, output_dir) in list(running.items()):
            returncode = process.poll()
            if returncode is None:
                continue
            handle.close()
            running.pop(token)
            if returncode != 0:
                (campaign_dir / "MINIMAL_REPAIR_FAILED").write_text(
                    f"{token}: exit {returncode}\n", encoding="utf-8"
                )
                raise RuntimeError(f"{token} failed with exit {returncode}")
            (output_dir / "GROUP_DONE").write_text(
                datetime.now(timezone.utc).isoformat(), encoding="utf-8"
            )
            log(f"completed {token}", log_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=Path("/root/mk_v2"))
    parser.add_argument("--environment", required=True, type=Path)
    parser.add_argument("--artifact-root", type=Path, default=Path("/"))
    parser.add_argument(
        "--shared-extensions",
        type=Path,
        default=Path("/root/autodl-tmp/shared_torch_extensions"),
    )
    parser.add_argument("--python", default="/root/miniconda3/bin/python")
    parser.add_argument("--max-parallel", type=int, default=3)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--smoke-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_parallel < 1:
        raise SystemExit("--max-parallel must be positive")
    campaign_dir = args.campaign_dir.resolve()
    log_path = campaign_dir / "orchestrator.log"
    args.shared_extensions.mkdir(parents=True, exist_ok=True)
    groups = preflight(
        campaign_dir,
        args.artifact_root.resolve(),
        args.repo.resolve(),
        args.environment.resolve(),
        log_path,
    )
    if not groups:
        raise SystemExit("campaign contains no repair groups")
    if args.preflight_only:
        log("preflight-only request completed", log_path)
        return
    run_smoke(
        args=args,
        group=max(groups, key=lambda value: value["test_cases"]),
        campaign_dir=campaign_dir,
        log_path=log_path,
    )
    (campaign_dir / "MINIMAL_REPAIR_SMOKE_DONE").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8"
    )
    if args.smoke_only:
        log("smoke-only request completed", log_path)
        return
    execute_groups(
        args=args,
        groups=groups,
        campaign_dir=campaign_dir,
        log_path=log_path,
    )
    (campaign_dir / "MINIMAL_REPAIR_ALL_DONE").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8"
    )
    log("all minimal repair groups completed", log_path)


if __name__ == "__main__":
    main()
