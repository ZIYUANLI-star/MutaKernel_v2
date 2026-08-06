#!/usr/bin/env python3
"""Wave-1.5 auto-relay orchestrator: fills every machine-producible blueprint
placeholder after Lane M closes, keeping the GPU serially busy.

Stage graph (markers in CAMP/wave15/, each stage idempotent + resumable):

  S0  wait LANE_M_DONE  (guard_lane_m writes it; fallback: plan exhausted)
  S1  freeze step: commit ops scripts into the repo, capture environment v3,
      archive the final Lane M ledger tarball
  S2  Lane D  - mutakernel-directed row, all wave-1 subjects (FSE runner)
  S3  subsets - derive Lane G / L-a / L-b subject subsets from Lane M ledger
  S4  Lane G  - legacy-oracle anchor + mutakernel-full rows on FAIL subjects
  S5  Lane L-a - LODO delta rows on non-detected subjects
  S6  Lane L-b - LODO full rows on detected subjects
  S7  Lane P  - B9 -> B7 -> B8 port batches + B11 batch (653 subjects)
  S8  Lane C6 - seeded-bug corpus campaign (requires run_c6_campaign.py;
      writes C6_BLOCKED and continues if the script is not yet deployed)
  S9  CHAIN_DONE

Wave-2 (C2 CUDA-L1) is a separate arm-and-fire pass once wave-1.5 closes
(user-deferred corpus; see design doc §W2).

Every stage writes STAGE_<name>_DONE on success; a failed stage retries up
to --max-retries with exponential backoff, then writes STAGE_<name>_BLOCKED
and STOPS the chain (never silently skips a data-bearing stage).
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
OPS = Path("/root/mk_v2_ops")
PYBIN = "/root/miniconda3/bin/python"

SUBJECTS = CAMP / "wave1_subject_manifest_v2.json"
ENV_V3 = W15 / "wave15_environment_v3.json"
MAP = RUNS / "e1" / "fault_to_stress_map.json"
MATRIX = MK / "configs" / "fse_e3_wave1_matrix.json"
ARTIFACT_ROOT = Path("/")

LOG = None


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    if LOG:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def marker(name: str) -> Path:
    return W15 / name


def sh(cmd, timeout=None, cwd=None, check=True):
    log(f"$ {' '.join(str(c) for c in cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, cwd=str(cwd or MK))
    if proc.stdout:
        log("stdout tail: " + proc.stdout[-1500:])
    if proc.returncode != 0:
        log(f"exit={proc.returncode} stderr tail: " + (proc.stderr or "")[-2000:])
        if check:
            raise RuntimeError(f"command failed ({proc.returncode})")
    return proc


def stage(name: str, max_retries: int = 3):
    """Decorator: marker-gated, retried, chain-stopping on exhaustion."""
    def wrap(fn):
        def run(*a, **kw):
            done = marker(f"STAGE_{name}_DONE")
            if done.exists():
                log(f"[{name}] already done")
                return True
            blocked = marker(f"STAGE_{name}_BLOCKED")
            if blocked.exists():
                blocked.unlink()  # operator relaunch clears the block
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


# ---------------------------------------------------------------------------
# FSE-runner lane execution (guarded restart loop, resume-safe)
# ---------------------------------------------------------------------------

def run_fse_lane(*, run_id: str, plan: Path, subjects: Path, out_dir: Path,
                 timeout_s: float = 180.0, max_restarts: int = 60,
                 subject_filter: Path = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    lane_log = out_dir.parent / f"{out_dir.name}.log"
    # CPU-parallel extension prewarm into this lane's cache tree (idempotent;
    # deterministic compile artifacts, verdict semantics untouched)
    prewarm = OPS / "prewarm_extensions.py"
    if prewarm.exists():
        env = dict(os.environ)
        env["PATH"] = "/usr/local/cuda/bin:" + env.get("PATH", "")
        with open(out_dir.parent / f"{out_dir.name}_prewarm.log", "a",
                  encoding="utf-8") as fh:
            subprocess.run(
                [PYBIN, "-u", str(prewarm), "--subjects", str(subjects),
                 "--run-dir", str(out_dir), "--jobs", "12"],
                stdout=fh, stderr=subprocess.STDOUT, cwd=str(MK), env=env)
    restarts = 0
    while True:
        cmd = [
            PYBIN, "-u", str(MK / "scripts" / "run_fse_experiment.py"),
            "--plan", str(plan),
            "--subjects", str(subjects),
            "--environment", str(ENV_V3),
            "--artifact-root", str(ARTIFACT_ROOT),
            "--output-dir", str(out_dir),
            "--run-id", run_id,
            "--device", "cuda",
            "--timeout", str(timeout_s),
            "--early-stop-on-fail",
        ]
        log(f"[lane {run_id}] runner start (restart {restarts}) -> {lane_log}")
        with open(lane_log, "a", encoding="utf-8") as fh:
            fh.write(f"\n===== runner start {datetime.now(timezone.utc).isoformat()} "
                     f"(restart {restarts}) =====\n")
            fh.flush()
            env = dict(os.environ)
            env["PATH"] = "/usr/local/cuda/bin:" + env.get("PATH", "")
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                  cwd=str(MK), env=env)
        if proc.returncode == 0:
            log(f"[lane {run_id}] runner exited cleanly")
            return
        restarts += 1
        if restarts > max_restarts:
            raise RuntimeError(f"lane {run_id}: restart cap exceeded")
        log(f"[lane {run_id}] runner exit={proc.returncode}; retry {restarts}")
        time.sleep(30)


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------

def wait_lane_m() -> None:
    """Block until Lane M is finished (marker or plan-exhausted heuristic)."""
    while True:
        if (CAMP / "LANE_M_DONE").exists():
            log("LANE_M_DONE marker present")
            return
        # fallback: runner absent AND guard reports completion in its log
        probe = subprocess.run(
            ["bash", "-c",
             "ps aux | grep run_fse_experiment | grep -v grep | wc -l"],
            capture_output=True, text=True)
        running = int(probe.stdout.strip() or "0")
        tail = subprocess.run(
            ["bash", "-c", f"tail -3 {CAMP}/guard_lane_m.log 2>/dev/null"],
            capture_output=True, text=True).stdout
        if running == 0 and "LANE_M_COMPLETE" in tail:
            log("guard reports LANE_M_COMPLETE")
            return
        time.sleep(120)


@stage("S1_FREEZE")
def s1_freeze():
    # 1. commit ops scripts into the repo for provenance
    scripts = ["build_wave15_lane_plans.py", "wave15_subset_analysis.py",
               "run_port_batch.py", "build_b9_tol_map.py",
               "wave15_orchestrator.py", "run_c6_campaign.py",
               "prewarm_extensions.py"]
    for name in scripts:
        src = OPS / name
        dst = MK / "scripts" / name
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    sh(["git", "add"] + [f"scripts/{n}" for n in scripts])
    dirty = sh(["git", "status", "--porcelain"], check=False).stdout.strip()
    if dirty:
        sh(["git", "-c", "user.name=mk-ops", "-c", "user.email=ops@mk.local",
            "commit", "-m",
            "wave-1.5: lane-plan builder, subset analysis, port batch, "
            "orchestrator (post-Lane-M freeze)"])
    # 2. capture environment v3 (with CUDA on PATH, clean tree)
    if not ENV_V3.exists():
        env = dict(os.environ)
        env["PATH"] = "/usr/local/cuda/bin:" + env.get("PATH", "")
        proc = subprocess.run(
            [PYBIN, str(MK / "scripts" / "capture_fse_environment.py"),
             "--output", str(ENV_V3)],
            capture_output=True, text=True, cwd=str(MK), env=env)
        if proc.returncode != 0:
            raise RuntimeError("environment capture failed: "
                               + (proc.stderr or "")[-1000:])
    # 3. archive the closed Lane M ledger
    tarball = CAMP / "lane_m_final_ledger.tar.gz"
    if not tarball.exists():
        sh(["bash", "-c",
            f"cd {CAMP} && tar czf {tarball} lane_m_run/observations.jsonl "
            f"lane_m_run/run_manifest.json lane_m_run.log guard_lane_m.log"])


@stage("S2_LANE_D")
def s2_lane_d():
    plan = W15 / "lane_d_plan.json"
    if not plan.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "mdir-plan",
            "--subjects", str(SUBJECTS),
            "--map", str(MAP),
            "--artifact-root", str(ARTIFACT_ROOT),
            "--out", str(plan)], timeout=3600)
    run_fse_lane(run_id="e3-wave15-lane-d-mdir-v1", plan=plan,
                 subjects=SUBJECTS, out_dir=W15 / "lane_d_run")


@stage("S3_SUBSETS")
def s3_subsets():
    sh([PYBIN, str(MK / "scripts" / "wave15_subset_analysis.py"),
        "--observations", str(CAMP / "lane_m_run" / "observations.jsonl"),
        "--subjects", str(SUBJECTS),
        "--out-dir", str(W15 / "subsets")], timeout=1800)


def _subset_nonempty(path: Path) -> bool:
    return path.exists() and path.read_text(encoding="utf-8").strip() != ""


@stage("S4_LANE_G")
def s4_lane_g():
    ids = W15 / "subsets" / "lane_g_subjects.txt"
    if not _subset_nonempty(ids):
        log("lane G subset empty — nothing to re-run (pure carryover)")
        return
    manifest = W15 / "lane_g_manifest.json"
    plan = W15 / "lane_g_plan.json"
    if not manifest.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "legacy-manifest",
            "--subjects", str(SUBJECTS),
            "--subject-ids", str(ids),
            "--out", str(manifest)], timeout=1800)
    if not plan.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "matrix-plan",
            "--subjects", str(manifest),
            "--matrix", str(MATRIX),
            "--strategy-names", "five-iid-historical-anchor", "mutakernel-full",
            "--matrix-id", "wave15-lane-g-legacy-v1",
            "--out", str(plan)], timeout=1800)
    run_fse_lane(run_id="e3-wave15-lane-g-legacy-v1", plan=plan,
                 subjects=manifest, out_dir=W15 / "lane_g_run")


@stage("S5_LANE_LA")
def s5_lane_la():
    ids = W15 / "subsets" / "lane_la_subjects.txt"
    if not _subset_nonempty(ids):
        log("lane L-a subset empty")
        return
    manifest = W15 / "lane_la_manifest.json"
    plan = W15 / "lane_la_plan.json"
    if not manifest.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "subset-manifest",
            "--subjects", str(SUBJECTS),
            "--subject-ids", str(ids),
            "--out", str(manifest)], timeout=1800)
    if not plan.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "lodo-plan", "--variant", "delta",
            "--subjects", str(manifest),
            "--matrix", str(MATRIX),
            "--out", str(plan)], timeout=3600)
    run_fse_lane(run_id="e3-wave15-lane-la-lodo-delta-v1", plan=plan,
                 subjects=manifest, out_dir=W15 / "lane_la_run")


@stage("S6_LANE_LB")
def s6_lane_lb():
    ids = W15 / "subsets" / "lane_lb_subjects.txt"
    if not _subset_nonempty(ids):
        log("lane L-b subset empty")
        return
    manifest = W15 / "lane_lb_manifest.json"
    plan = W15 / "lane_lb_plan.json"
    if not manifest.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "subset-manifest",
            "--subjects", str(SUBJECTS),
            "--subject-ids", str(ids),
            "--out", str(manifest)], timeout=1800)
    if not plan.exists():
        sh([PYBIN, str(MK / "scripts" / "build_wave15_lane_plans.py"),
            "lodo-plan", "--variant", "full",
            "--subjects", str(manifest),
            "--matrix", str(MATRIX),
            "--out", str(plan)], timeout=3600)
    run_fse_lane(run_id="e3-wave15-lane-lb-lodo-full-v1", plan=plan,
                 subjects=manifest, out_dir=W15 / "lane_lb_run")


@stage("S7_LANE_P", max_retries=2)
def s7_lane_p():
    tol_map = W15 / "b9_tol_map.json"
    if not tol_map.exists():
        sh([PYBIN, str(MK / "scripts" / "build_b9_tol_map.py"),
            "--calib-dir", str(RUNS / "e3_b9_calib"),
            "--out", str(tol_map)], timeout=600)
    for baseline in ("b9", "b7", "b8", "b11"):
        done_marker = marker(f"LANE_P_{baseline.upper()}_DONE")
        if done_marker.exists():
            continue
        cmd = [PYBIN, "-u", str(MK / "scripts" / "run_port_batch.py"),
               "--baseline", baseline,
               "--subjects", str(SUBJECTS),
               "--artifact-root", str(ARTIFACT_ROOT),
               "--out-dir", str(W15 / f"lane_p_{baseline}")]
        if baseline == "b9":
            cmd += ["--b9-tol-map", str(tol_map)]
        lane_log = W15 / f"lane_p_{baseline}.log"
        with open(lane_log, "a", encoding="utf-8") as fh:
            env = dict(os.environ)
            env["PATH"] = "/usr/local/cuda/bin:" + env.get("PATH", "")
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                  cwd=str(MK), env=env)
        if proc.returncode != 0:
            raise RuntimeError(f"port batch {baseline} failed "
                               f"(exit {proc.returncode}); see {lane_log}")
        done_marker.write_text(datetime.now(timezone.utc).isoformat(),
                               encoding="utf-8")


@stage("S8_LANE_C6", max_retries=1)
def s8_lane_c6():
    script = MK / "scripts" / "run_c6_campaign.py"
    if not script.exists():
        marker("C6_BLOCKED_SCRIPT_MISSING").write_text(
            datetime.now(timezone.utc).isoformat(), encoding="utf-8")
        log("C6 runner not deployed yet — marked blocked, chain continues")
        return
    lane_log = W15 / "lane_c6.log"
    with open(lane_log, "a", encoding="utf-8") as fh:
        env = dict(os.environ)
        env["PATH"] = "/usr/local/cuda/bin:" + env.get("PATH", "")
        proc = subprocess.run(
            [PYBIN, "-u", str(script), "drive",
             "--corpus-root", str(MK / "external" / "C6_gpuemu"),
             "--out-dir", str(W15 / "lane_c6"),
             "--timeout", "1800"],
            stdout=fh, stderr=subprocess.STDOUT, cwd=str(MK), env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"C6 campaign failed; see {lane_log}")


def main():
    global LOG
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-wait", action="store_true",
                    help="do not wait for LANE_M_DONE (testing only)")
    args = ap.parse_args()

    W15.mkdir(parents=True, exist_ok=True)
    LOG = W15 / "orchestrator.log"

    lock = W15 / "orchestrator.pid"
    if lock.exists():
        old_pid = lock.read_text().strip()
        if old_pid and Path(f"/proc/{old_pid}").exists():
            print(f"another orchestrator is alive (pid {old_pid}); exiting")
            return 1
    lock.write_text(str(os.getpid()), encoding="utf-8")

    log("=== wave-1.5 orchestrator start ===")
    if not args.skip_wait:
        wait_lane_m()

    for fn in (s1_freeze, s2_lane_d, s3_subsets, s4_lane_g,
               s5_lane_la, s6_lane_lb, s7_lane_p, s8_lane_c6):
        if not fn():
            log("chain stopped at a blocked stage")
            return 2

    marker("CHAIN_DONE").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    log("=== CHAIN_DONE: all wave-1.5 GPU lanes complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
