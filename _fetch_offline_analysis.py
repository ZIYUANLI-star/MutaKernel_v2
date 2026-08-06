"""Read-only SFTP pull of E1 observation/manifest files for offline analysis.

Destination: MutakernelV2/实验/重跑实验数据/离线分析/data/e1/
Never writes anything to the remote side.
"""
import os
from pathlib import Path

from _remote import connect

REMOTE_DIR = "/root/mk_v2_runs/e1"
LOCAL_DIR = Path("MutakernelV2/实验/重跑实验数据/离线分析/data/e1")

FILES = [
    "equiv_observations.jsonl",
    "baseline_observations.jsonl",
    "cse_observations_lane0.jsonl",
    "cse_observations_lane1.jsonl",
    "cse_observations_lane2.jsonl",
    "cse_observations_lane3.jsonl",
    "cse_observations_lane4.jsonl",
    "cse_observations_lane5.jsonl",
    "cse_observations_lane0_timeout_v1.jsonl",
    "cse_observations_env_v1.jsonl",
    "baseline_run_manifest.json",
    "baseline_summary.json",
    "equiv_run_manifest.json",
    "equiv_run_manifest_lane0.json",
    "equiv_run_manifest_lane1.json",
    "equiv_run_manifest_lane2.json",
    "equiv_run_manifest_lane3.json",
    "equiv_run_manifest_lane4_requeue.json",
    "equiv_summary.json",
    "cse_run_manifest_lane0.json",
    "cse_run_manifest_lane1.json",
    "cse_run_manifest_lane2.json",
    "cse_run_manifest_lane3.json",
    "cse_run_manifest_lane4.json",
    "cse_run_manifest_lane5.json",
    "cse_summary_lane1.json",
    "cse_summary_lane2.json",
    "original_controls.json",
    "probe_manifest.json",
    "lane_plan.json",
    "cse_lane_plan.json",
]


def main():
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    client = connect()
    sftp = client.open_sftp()
    for name in FILES:
        remote = f"{REMOTE_DIR}/{name}"
        local = LOCAL_DIR / name
        try:
            attrs = sftp.stat(remote)
        except FileNotFoundError:
            print(f"SKIP (missing): {name}")
            continue
        sftp.get(remote, str(local))
        ok = local.stat().st_size == attrs.st_size
        print(f"{'OK ' if ok else 'SIZE MISMATCH '}{name}: {attrs.st_size} bytes")
    sftp.close()
    client.close()
    print("FETCH_DONE")


if __name__ == "__main__":
    main()
