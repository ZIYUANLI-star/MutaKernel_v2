#!/usr/bin/env python3
"""Wave-2 + fidelity auto-relay orchestrator.

Arms behind the wave-1.5 chain: waits for CAMP/wave15/CHAIN_DONE, then runs

  W1  freeze: commit wave-2 ops scripts, archive prep artifacts
  W2  port fidelity: B7 (robust-kbench highlighted, 8 kernels),
      B8 (KernelBenchX kbx_corpus, 110 states), B9 aggregation vs Lane C6
  W3  B9 L3 calibration (50 tasks x fp32/fp16 = 100 units, driver v2 queue)
  W4  L3 tolerance map
  W5  Lane M2  - six strategy rows x 100 wave-2 subjects (16,400 cases)
  W6  Lane D2  - M-dir row x 100 subjects (3,000 cases)
  W7  subsets2 - Lane G2 / L2-a / L2-b subject subsets from Lane M2 ledger
  W8  Lane G2  - legacy-oracle rows on FAIL subjects
  W9  Lane L2a - LODO delta rows on non-detected subjects
  W10 Lane L2b - LODO full rows on detected subjects
  W11 Lane P2  - B9/B7/B8 ports + B11 on 100 wave-2 subjects
  W12 offline  - power-analysis parameters + equal-time curves + fidelity
      merge (CPU)
  WAVE2_DONE

Same discipline as wave-1.5: markers, retries, blocked-stop, append-only
ledgers, full worker logs, replay bundles.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

MK = Path("/root/mk_v2")
RUNS = Path("/root/mk_v2_runs")
CAMP = RUNS / "e3_campaign"
W15 = CAMP / "wave15"
W2 = CAMP / "wave2"
OPS = Path("/root/mk_v2_ops")
PYBIN = "/root/miniconda3/bin/python"

SUBJECTS2 = CAMP / "wave2_subject_manifest.json"
LANE_M2_PLAN = CAMP / "wave2_lane_m_plan.json"
MDIR2_PLAN = CAMP / "wave2_mdir_plan.json"
L3_SIGNED = RUNS / "e2_reconcile" / "contracts_l3_signed_v2.jsonl"
# wave-2 lanes must validate against an environment captured AFTER the W1
# freeze commit (the commit hash changes there); ENV_V3 belongs to wave-1.5.
ENV_V4 = W2 / "wave2_environment_v4.json"
MATRIX = MK / "configs" / "fse_e3_wave1_matrix.json"
CALIB_L3 = RUNS / "e3_b9_calib_l3"
ARTIFACT_ROOT = Path("/")

LOG = None


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    if LOG:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def marker(name: str) -> Path:
    return W2 / name


def sh(cmd, timeout=None, cwd=None, check=True, env=None):
    log(f"$ {' '.join(str(c) for c in cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, cwd=str(cwd or MK), env=env)
    if proc.stdout:
        log("stdout tail: " + proc.stdout[-1500:])
    if proc.returncode != 0:
        log(f"exit={proc.returncode} stderr tail: "
            + (proc.stderr or "")[-2000:])
        if check:
            raise RuntimeError(f"command failed ({proc.returncode})")
    return proc


def cuda_env():
    env = dict(os.environ)
    env["PATH"] = "/usr/local/cuda/bin:" + env.get("PATH", "")
    return env


def stage(name: str, max_retries: int = 3):
    def wrap(fn):
        def run(*a, **kw):
            done = marker(f"STAGE_{name}_DONE")
            if done.exists():
                log(f"[{name}] already done")
                return True
            blocked = marker(f"STAGE_{name}_BLOCKED")
            if blocked.exists():
                blocked.unlink()
            for attempt in range(1, max_retries + 1):
                try:
                    log(f"[{name}] attempt {attempt}")
                    fn(*a, **kw)
                    done.write_text(datetime.now(timezone.utc).isoformat(),
                                    encoding="utf-8")
                    log(f"[{name}] DONE")
                    return True
                except Exception as exc:  # noqa: BLE001
                    log(f"[{name}] attempt {attempt} failed: {exc!r}")
                    time.sleep(min(600, 60 * attempt))
            blocked.write_text(datetime.now(timezone.utc).isoformat(),
                               encoding="utf-8")
            log(f"[{name}] BLOCKED after {max_retries} attempts — chain stops")
            return False
        return run
    return wrap


def run_fse_lane(*, run_id: str, plan: Path, subjects: Path, out_dir: Path,
                 timeout_s: float = 180.0, max_restarts: int = 60) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    lane_log = out_dir.parent / f"{out_dir.name}.log"
    # CPU-parallel extension prewarm into this lane's cache tree (idempotent;
    # compile artifacts are deterministic, verdict semantics untouched)
    prewarm = OPS / "prewarm_extensions.py"
    if prewarm.exists():
        with open(out_dir.parent / f"{out_dir.name}_prewarm.log", "a",
                  encoding="utf-8") as fh:
            subprocess.run(
                [PYBIN, "-u", str(prewarm), "--subjects", str(subjects),
                 "--run-dir", str(out_dir), "--jobs", "12"],
                stdout=fh, stderr=subprocess.STDOUT, cwd=str(MK),
                env=cuda_env())
    restarts = 0
    while True:
        cmd = [
            PYBIN, "-u", str(MK / "scripts" / "run_fse_experiment.py"),
            "--plan", str(plan),
            "--subjects", str(subjects),
            "--environment", str(ENV_V4),
            "--artifact-root", str(ARTIFACT_ROOT),
            "--output-dir", str(out_dir),
            "--run-id", run_id,
            "--device", "cuda",
            "--timeout", str(timeout_s),
            "--early-stop-on-fail",
        ]
        log(f"[lane {run_id}] runner start (restart {restarts}) -> {lane_log}")
        with open(lane_log, "a", encoding="utf-8") as fh:
            fh.write(f"\n===== runner start "
                     f"{datetime.now(timezone.utc).isoformat()} "
                     f"(restart {restarts}) =====\n")
            fh.flush()
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                  cwd=str(MK), env=cuda_env())
        if proc.returncode == 0:
            log(f"[lane {run_id}] runner exited cleanly")
            return
        restarts += 1
        if restarts > max_restarts:
            raise RuntimeError(f"lane {run_id}: restart cap exceeded")
        log(f"[lane {run_id}] runner exit={proc.returncode}; retry {restarts}")
        time.sleep(30)


def wait_chain_done() -> None:
    while True:
        if (W15 / "CHAIN_DONE").exists():
            log("wave-1.5 CHAIN_DONE present")
            return
        time.sleep(120)


# ---------------------------------------------------------------- stages
@stage("W1_FREEZE")
def w1_freeze():
    scripts = ["wave2_prep.py", "run_port_fidelity.py",
               "offline_close_analysis.py", "wave2_orchestrator.py",
               "prewarm_extensions.py"]
    for name in scripts:
        (MK / "scripts" / name).write_text(
            (OPS / name).read_text(encoding="utf-8"), encoding="utf-8")
    sh(["git", "add"] + [f"scripts/{n}" for n in scripts])
    dirty = sh(["git", "status", "--porcelain"], check=False).stdout.strip()
    if dirty:
        sh(["git", "-c", "user.name=mk-ops", "-c", "user.email=ops@mk.local",
            "commit", "-m",
            "wave-2: prep chain, port fidelity, offline analysis, "
            "orchestrator (post-wave-1.5 freeze)"])
    leftover = sh(["git", "status", "--porcelain"], check=False).stdout.strip()
    if leftover:
        raise RuntimeError(f"worktree still dirty after freeze: {leftover!r}")
    # capture environment v4 AFTER the commit so the hash matches the lanes
    if not ENV_V4.exists():
        proc = subprocess.run(
            [PYBIN, str(MK / "scripts" / "capture_fse_environment.py"),
             "--output", str(ENV_V4)],
            capture_output=True, text=True, cwd=str(MK), env=cuda_env())
        if proc.returncode != 0:
            raise RuntimeError("environment v4 capture failed: "
                               + (proc.stderr or "")[-1000:])


@stage("W2_FIDELITY", max_retries=2)
def w2_fidelity():
    fid = W2 / "fidelity"
    for name, extra in (("b7", []), ("b8", [])):
        done = marker(f"FIDELITY_{name.upper()}_DONE")
        if done.exists():
            continue
        lane_log = fid / f"{name}.log"
        fid.mkdir(parents=True, exist_ok=True)
        with open(lane_log, "a", encoding="utf-8") as fh:
            proc = subprocess.run(
                [PYBIN, "-u", str(MK / "scripts" / "run_port_fidelity.py"),
                 name, "--out-dir", str(fid / name)] + extra,
                stdout=fh, stderr=subprocess.STDOUT, cwd=str(MK),
                env=cuda_env())
        if proc.returncode != 0:
            raise RuntimeError(f"fidelity {name} failed; see {lane_log}")
        done.write_text(datetime.now(timezone.utc).isoformat(),
                        encoding="utf-8")
    # B9: offline aggregation against Lane C6 output
    sh([PYBIN, str(MK / "scripts" / "run_port_fidelity.py"), "b9-aggregate",
        "--c6-dir", str(W15 / "lane_c6"),
        "--out-dir", str(fid / "b9")], timeout=600)


@stage("W3_B9_L3_CALIB", max_retries=2)
def w3_b9_l3_calib():
    CALIB_L3.mkdir(parents=True, exist_ok=True)
    queue = CALIB_L3 / "queue_state.json"
    if not queue.exists():
        units = {}
        for line in L3_SIGNED.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            task_id = r["task_id"]            # e.g. L3_P1
            task_file = r["extraction"]["source"]
            for dtype in ("float32", "float16"):
                uid = f"{task_id}__{dtype}"
                units[uid] = {
                    "unit": uid, "task_key": task_id, "dtype": dtype,
                    "task_file": task_file,
                    "reduction_heavy": True,
                    "out_numel": None, "in_numel": None,
                    "est_peak_gb": 20.0, "reserve_gb": 30.0,
                    "est_wall_s_fast": 300, "est_wall_s_slow": 1200,
                    "unit_timeout_s": 7200,
                    "above_quantile_limit": False,
                    "previous_status": None,
                }
        state = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "wave": "l3_wave2",
            "scope_decision": "wave-2 KB_L3 calibration "
                              "(e3_campaign_scope_v1 wave2)",
            "pending": sorted(units),
            "claimed": {},
            "done": {},
            "units": units,
            "stage2_deferred": [],
        }
        queue.write_text(json.dumps(state, indent=1), encoding="utf-8")
        log(f"L3 calib queue built: {len(units)} units")
    lane_log = CALIB_L3 / "driver_lane0.log"
    with open(lane_log, "a", encoding="utf-8") as fh:
        proc = subprocess.run(
            [PYBIN, "-u", str(MK / "_b9_calib_driver_v2.py"),
             "--lane", "0", "--out-root", str(CALIB_L3),
             "--budget-gb", "100"],
            stdout=fh, stderr=subprocess.STDOUT, cwd=str(MK), env=cuda_env())
    if proc.returncode != 0:
        raise RuntimeError(f"L3 calib driver failed; see {lane_log}")
    state = json.loads(queue.read_text("utf-8"))
    if state["pending"] or state["claimed"]:
        raise RuntimeError(
            f"L3 calib incomplete: pending={len(state['pending'])} "
            f"claimed={len(state['claimed'])}")


@stage("W4_TOLMAP_L3")
def w4_tolmap_l3():
    sh([PYBIN, str(MK / "scripts" / "build_b9_tol_map.py"),
        "--calib-dir", str(CALIB_L3),
        "--out", str(W2 / "b9_tol_map_l3.json")], timeout=600)


@stage("W5_LANE_M2")
def w5_lane_m2():
    run_fse_lane(run_id="e3-wave2-lane-m2-v1", plan=LANE_M2_PLAN,
                 subjects=SUBJECTS2, out_dir=W2 / "lane_m2_run")


@stage("W6_LANE_D2")
def w6_lane_d2():
    run_fse_lane(run_id="e3-wave2-lane-d2-mdir-v1", plan=MDIR2_PLAN,
                 subjects=SUBJECTS2, out_dir=W2 / "lane_d2_run")


@stage("W7_SUBSETS2")
def w7_subsets2():
    sh([PYBIN, str(MK / "scripts" / "wave15_subset_analysis.py"),
        "--observations", str(W2 / "lane_m2_run" / "observations.jsonl"),
        "--subjects", str(SUBJECTS2),
        "--out-dir", str(W2 / "subsets")], timeout=1800)


def _subset_nonempty(path: Path) -> bool:
    return path.exists() and path.read_text(encoding="utf-8").strip() != ""


@stage("W8_LANE_G2")
def w8_lane_g2():
    ids = W2 / "subsets" / "lane_g_subjects.txt"
    if not _subset_nonempty(ids):
        log("lane G2 subset empty — pure carryover")
        return
    manifest = W2 / "lane_g2_manifest.json"
    plan = W2 / "lane_g2_plan.json"
    if not manifest.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "legacy-manifest", "--subjects", str(SUBJECTS2),
            "--subject-ids", str(ids), "--out", str(manifest)], timeout=1800)
    if not plan.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "matrix-plan", "--subjects", str(manifest),
            "--matrix", str(MATRIX),
            "--strategy-names", "five-iid-historical-anchor",
            "mutakernel-full",
            "--matrix-id", "wave2-lane-g2-legacy-v1",
            "--out", str(plan)], timeout=1800)
    run_fse_lane(run_id="e3-wave2-lane-g2-legacy-v1", plan=plan,
                 subjects=manifest, out_dir=W2 / "lane_g2_run")


@stage("W9_LANE_L2A")
def w9_lane_l2a():
    ids = W2 / "subsets" / "lane_la_subjects.txt"
    if not _subset_nonempty(ids):
        log("lane L2-a subset empty")
        return
    manifest = W2 / "lane_l2a_manifest.json"
    plan = W2 / "lane_l2a_plan.json"
    if not manifest.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "subset-manifest", "--subjects", str(SUBJECTS2),
            "--subject-ids", str(ids), "--out", str(manifest)], timeout=1800)
    if not plan.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "lodo-plan", "--variant", "delta", "--subjects", str(manifest),
            "--matrix", str(MATRIX), "--out", str(plan)], timeout=3600)
    run_fse_lane(run_id="e3-wave2-lane-l2a-lodo-delta-v1", plan=plan,
                 subjects=manifest, out_dir=W2 / "lane_l2a_run")


@stage("W10_LANE_L2B")
def w10_lane_l2b():
    ids = W2 / "subsets" / "lane_lb_subjects.txt"
    if not _subset_nonempty(ids):
        log("lane L2-b subset empty")
        return
    manifest = W2 / "lane_l2b_manifest.json"
    plan = W2 / "lane_l2b_plan.json"
    if not manifest.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "subset-manifest", "--subjects", str(SUBJECTS2),
            "--subject-ids", str(ids), "--out", str(manifest)], timeout=1800)
    if not plan.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "lodo-plan", "--variant", "full", "--subjects", str(manifest),
            "--matrix", str(MATRIX), "--out", str(plan)], timeout=3600)
    run_fse_lane(run_id="e3-wave2-lane-l2b-lodo-full-v1", plan=plan,
                 subjects=manifest, out_dir=W2 / "lane_l2b_run")


@stage("W11_LANE_P2", max_retries=2)
def w11_lane_p2():
    tol_map = W2 / "b9_tol_map_l3.json"
    for baseline in ("b9", "b7", "b8", "b11"):
        done_marker = marker(f"LANE_P2_{baseline.upper()}_DONE")
        if done_marker.exists():
            continue
        cmd = [PYBIN, "-u", str(MK / "scripts" / "run_port_batch.py"),
               "--baseline", baseline,
               "--subjects", str(SUBJECTS2),
               "--artifact-root", str(ARTIFACT_ROOT),
               "--out-dir", str(W2 / f"lane_p2_{baseline}")]
        if baseline == "b9":
            cmd += ["--b9-tol-map", str(tol_map)]
        lane_log = W2 / f"lane_p2_{baseline}.log"
        with open(lane_log, "a", encoding="utf-8") as fh:
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                  cwd=str(MK), env=cuda_env())
        if proc.returncode != 0:
            raise RuntimeError(f"port batch {baseline} failed; see {lane_log}")
        done_marker.write_text(datetime.now(timezone.utc).isoformat(),
                               encoding="utf-8")


@stage("W12_OFFLINE")
def w12_offline():
    off = W2 / "offline"
    off.mkdir(parents=True, exist_ok=True)
    ledgers = [
        CAMP / "lane_m_run" / "observations.jsonl",
        W15 / "lane_d_run" / "observations.jsonl",
        W2 / "lane_m2_run" / "observations.jsonl",
        W2 / "lane_d2_run" / "observations.jsonl",
    ]
    ledgers = [str(p) for p in ledgers if Path(p).exists()]
    sh([PYBIN, str(MK / "scripts" / "offline_close_analysis.py"), "power",
        "--subjects", str(CAMP / "wave1_subject_manifest_v2.json"),
        str(SUBJECTS2),
        "--ledgers"] + ledgers +
       ["--out", str(off / "power_analysis.json")], timeout=1800)
    sh([PYBIN, str(MK / "scripts" / "offline_close_analysis.py"), "equaltime",
        "--ledgers"] + ledgers +
       ["--out", str(off / "equaltime_curves.json")], timeout=1800)
    sh([PYBIN, str(MK / "scripts" / "offline_close_analysis.py"), "fidelity",
        "--b7", str(W2 / "fidelity" / "b7" / "b7_fidelity_summary.json"),
        "--b8", str(W2 / "fidelity" / "b8" / "b8_fidelity_summary.json"),
        "--b9", str(W2 / "fidelity" / "b9" / "b9_fidelity_summary.json"),
        "--out", str(off / "port_fidelity_summary.json")], timeout=600)


def main():
    global LOG
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-wait", action="store_true")
    args = ap.parse_args()

    W2.mkdir(parents=True, exist_ok=True)
    LOG = W2 / "orchestrator.log"

    lock = W2 / "orchestrator.pid"
    if lock.exists():
        old_pid = lock.read_text().strip()
        if old_pid and Path(f"/proc/{old_pid}").exists():
            print(f"another wave2 orchestrator alive (pid {old_pid}); exit")
            return 1
    lock.write_text(str(os.getpid()), encoding="utf-8")

    log("=== wave-2 orchestrator start ===")
    if not args.skip_wait:
        wait_chain_done()

    for fn in (w1_freeze, w2_fidelity, w3_b9_l3_calib, w4_tolmap_l3,
               w5_lane_m2, w6_lane_d2, w7_subsets2, w8_lane_g2,
               w9_lane_l2a, w10_lane_l2b, w11_lane_p2, w12_offline):
        if not fn():
            log("wave-2 chain stopped at a blocked stage")
            return 2

    marker("WAVE2_DONE").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    log("=== WAVE2_DONE: wave-2 + fidelity complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
