#!/usr/bin/env python3
"""E1 final exclusive-window settlement orchestrator (deployed 2026-07-29).

Fired ONCE by _final_window_trigger.sh when the CSE_DONE_LANE3 marker file
appears.  Serial steps, one driver at a time, whole GPU (frac 0.92):

  0. preconditions: lane3 driver process exited; guard v10.1 exited (it
     self-exits in the same cycle it writes CSE_DONE_LANE3, because lane4/5
     markers already exist -> it touches CSE_DONE and exits; its pgrep
     pattern '--lane N$' can never match our '--lane-tag ...' drivers, so
     even a lingering guard cannot restart anything);
  1a. ledger requeue of L1_P96__launch_config_mutate__0 (archive the
      INCONCLUSIVE obs line verbatim into cse_observations_inc_archive_v2
      + drop the id from cse_completed_lane3.json, with .bak backups)
      -> driver --lane 3 --lane-tag p96_5400 --timeout 5400;
  1b. same for the 5 remaining lane3 ids (3x P53 legit-rejection family,
      P52/P46 transient-OOM family) -> --lane 3 --lane-tag final_requeue
      --timeout 3600 (P53 per-kernel policy skip auto-discovered from
      cse_policy_skip.json);
  1c. same for L1_P23__mask_boundary__1 (lane5 collateral OOM kill)
      -> --lane 5 --lane-tag final_requeue --timeout 3600;
  2. targeted review of flip candidate #7 L1_P46__index_replace__5
     (FALSIFIED witness mixed_extremes/sub1/seed50041 was really a 90s
     round-watchdog timeout): 3x candidate reruns with round_timeout=300
     (stress seed = base_seed + equiv_runs + si, so equiv_runs=0 +
     base_seed=50040 reproduces production seeds 50040/50041/50042
     bit-exactly, policy-list independent) + 1x unmutated control.
     EVIDENCE + RECOMMENDATION FILES ONLY - the main ledger is NOT touched;
  3. equiv crash retry of L1_P95__relop_replace__5 (CUDA illegal memory
     access, wall 61s): 1x candidate mirroring the original equiv protocol
     + 1x unmutated control; offline grade_equiv_evidence for the proposal.
     EVIDENCE + RECOMMENDATION FILES ONLY - the main ledger is NOT touched;
  4. touch FINAL_WINDOW_DONE with a summary.

Grading semantics are never modified.  Requeue observations live in their
own tagged files (cse_observations_lane3_p96_5400.jsonl etc.) which still
match the cse_observations_lane*.jsonl aggregation glob, so the final merge
picks them up; archived INCONCLUSIVE originals are preserved verbatim.
Idempotent: every step no-ops if its outputs already exist, so the trigger
can safely retry after a partial failure.  --dry-run walks every step in
echo mode (no ledger writes, no GPU work) for the end-to-end drill.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

MK = Path("/root/mk_v2")
RUNS = Path("/root/mk_v2_runs")
E1 = RUNS / "e1"
PY = "/root/miniconda3/bin/python"
LOGF = RUNS / "final_window.log"
MARK = E1 / "CSE_DONE_LANE3"
DONE = E1 / "FINAL_WINDOW_DONE"
GUARD_PIDFILE = RUNS / "e1_guard.pid"
ARCHIVE = E1 / "cse_observations_inc_archive_v2.jsonl"
REVIEW = E1 / "final_window_review"
BAK_SUFFIX = ".bak_final_window"
LANE3_DRIVER_PAT = r"run_e1_cse_falsify\.py.*--lane 3$"

# (stage_label, lane, lane_tag, per-probe timeout, ids) - strictly serial.
STAGES = [
    ("1a_p96", 3, "p96_5400", 5400,
     ["L1_P96__launch_config_mutate__0"]),
    ("1b_lane3", 3, "final_requeue", 3600,
     ["L1_P53__arith_replace__17",
      "L1_P53__relop_replace__4",
      "L1_P53__const_perturb__0",
      "L1_P52__arith_replace__11",
      "L1_P46__relop_replace__5"]),
    ("1c_lane5", 5, "final_requeue", 3600,
     ["L1_P23__mask_boundary__1"]),
]

DRY = "--dry-run" in sys.argv


def log(msg: str) -> None:
    tag = " [DRY-RUN]" if DRY else ""
    line = f"[final_window {datetime.now().strftime('%F %T')}]{tag} {msg}"
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def pgrep(pattern: str) -> list[int]:
    r = subprocess.run(["pgrep", "-f", pattern],
                       capture_output=True, text=True)
    return [int(x) for x in r.stdout.split()]


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


# ---------------------------------------------------------------------------
# Step 0: preconditions
# ---------------------------------------------------------------------------

def step0_preconditions() -> None:
    log(f"step0: marker {MARK} exists={MARK.exists()}")
    if not DRY and not MARK.exists():
        raise RuntimeError("CSE_DONE_LANE3 marker missing - refusing to run")

    # lane3 driver must be gone (never interfere with a live lane3).
    deadline = time.time() + 1800
    while True:
        pids = pgrep(LANE3_DRIVER_PAT)
        if not pids:
            log("step0: lane3 driver process gone (ok)")
            break
        if DRY:
            log(f"step0: lane3 driver still running pids={pids} "
                "(expected during the drill; real run would wait)")
            break
        if time.time() > deadline:
            raise RuntimeError(f"lane3 driver still alive after 30min: {pids}")
        log(f"step0: lane3 driver still up {pids}, waiting 15s ...")
        time.sleep(15)

    # guard v10.1 self-exits once all three markers exist (same cycle it
    # touches CSE_DONE_LANE3, since lane4/5 markers are already present).
    gpid = None
    if GUARD_PIDFILE.exists():
        try:
            gpid = int(GUARD_PIDFILE.read_text().strip())
        except ValueError:
            gpid = None
    if gpid is None or not pid_alive(gpid):
        log("step0: guard already exited (pidfile gone or pid dead) (ok)")
    elif DRY:
        log(f"step0: guard alive pid={gpid} (expected during the drill; "
            "real run would wait for its self-exit)")
    else:
        deadline = time.time() + 900
        while pid_alive(gpid) and time.time() < deadline:
            log(f"step0: guard pid={gpid} still up, waiting 30s for its "
                "self-exit (cycle is 120s) ...")
            time.sleep(30)
        if pid_alive(gpid):
            log(f"step0: WARN guard pid={gpid} did not exit in 15min; "
                "continuing anyway - CSE_DONE_LANE3 blocks any lane restart "
                "and its pgrep pattern cannot match --lane-tag drivers")
        else:
            log("step0: guard exited (ok)")

    for m in ("CSE_DONE_LANE3", "CSE_DONE_LANE4", "CSE_DONE_LANE5",
              "CSE_DONE"):
        log(f"step0: marker {m} exists={(E1 / m).exists()}")
    r = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used,memory.total",
         "--format=csv,noheader"], capture_output=True, text=True)
    log(f"step0: gpu memory snapshot: {r.stdout.strip()}")


# ---------------------------------------------------------------------------
# Step 1: ledger requeue (archive INCONCLUSIVE lines + drop completed ids)
# ---------------------------------------------------------------------------

def requeue_ledger(lane: int, ids: list[str]) -> None:
    obs = E1 / f"cse_observations_lane{lane}.jsonl"
    comp = E1 / f"cse_completed_lane{lane}.json"
    idset = set(ids)

    for p in (obs, comp):
        bak = p.with_name(p.name + BAK_SUFFIX)
        if not bak.exists():
            if DRY:
                log(f"ledger: would back up {p.name} -> {bak.name}")
            else:
                shutil.copy2(p, bak)
                log(f"ledger: backup {bak.name} written")

    lines = obs.read_text(encoding="utf-8").splitlines()
    keep, moved = [], []
    for ln in lines:
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            keep.append(ln)
            continue
        if (rec.get("probe_id") in idset
                and rec.get("outcome") == "INCONCLUSIVE"):
            moved.append(ln)
        else:
            keep.append(ln)
    moved_ids = {json.loads(m)["probe_id"] for m in moved}
    already = [i for i in ids if i not in moved_ids]

    comp_ids = json.loads(comp.read_text(encoding="utf-8"))
    comp_drop = [i for i in ids if i in comp_ids]

    log(f"ledger lane{lane}: {len(moved)} INCONCLUSIVE lines to archive "
        f"{sorted(moved_ids)}; drop from completed: {comp_drop}; "
        f"already processed earlier: {already}")
    if DRY:
        return

    if already:
        # Idempotent re-run: each id must already sit in the archive.
        arch = ARCHIVE.read_text(encoding="utf-8") if ARCHIVE.exists() else ""
        for i in already:
            if f'"{i}"' not in arch:
                raise RuntimeError(
                    f"{i}: neither INCONCLUSIVE in {obs.name} nor archived "
                    f"in {ARCHIVE.name} - refusing to continue")

    if moved:
        with open(ARCHIVE, "a", encoding="utf-8") as fh:
            for m in moved:
                fh.write(m + "\n")
        tmp = obs.with_name(obs.name + ".tmp")
        tmp.write_text("\n".join(keep) + ("\n" if keep else ""),
                       encoding="utf-8")
        os.replace(tmp, obs)
        log(f"ledger lane{lane}: obs {len(lines)} -> {len(keep)} lines, "
            f"{len(moved)} archived verbatim to {ARCHIVE.name}")

    if comp_drop:
        new_comp = sorted(set(comp_ids) - idset)
        tmp = comp.with_name(comp.name + ".tmp")
        tmp.write_text(json.dumps(new_comp), encoding="utf-8")
        os.replace(tmp, comp)
        log(f"ledger lane{lane}: completed {len(comp_ids)} -> "
            f"{len(new_comp)} ids")


def run_requeue_driver(stage: str, lane: int, tag: str, timeout: int,
                       ids: list[str]) -> None:
    dlog = RUNS / f"final_window_{stage}.log"
    cmd = [PY, "-u", "scripts/run_e1_cse_falsify.py",
           "--out-dir", str(E1),
           "--kernelbench-root", "KernelBench",
           "--timeout", str(timeout),
           "--lane-plan", str(E1 / "cse_lane_plan.json"),
           "--lane", str(lane), "--lane-tag", tag]
    log(f"driver {stage}: {' '.join(cmd)} (frac 0.92, log {dlog.name})")
    if DRY:
        return
    with open(dlog, "ab") as fh:
        rc = subprocess.run(cmd, cwd=str(MK), stdout=fh,
                            stderr=subprocess.STDOUT).returncode
    log(f"driver {stage}: exit={rc}")
    if rc != 0:
        raise RuntimeError(f"driver {stage} failed rc={rc}")

    obs = E1 / f"cse_observations_lane{lane}_{tag}.jsonl"
    outcomes = {}
    if obs.exists():
        for ln in obs.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
                outcomes[r["probe_id"]] = r.get("outcome")
            except json.JSONDecodeError:
                pass
    missing = [i for i in ids if i not in outcomes]
    for i in ids:
        log(f"driver {stage}:   {i}: {outcomes.get(i, 'MISSING')}")
        if outcomes.get(i) == "INCONCLUSIVE":
            log(f"driver {stage}:   WARN {i} INCONCLUSIVE again - left for "
                "human adjudication (no auto-retry, semantics untouched)")
    if missing:
        raise RuntimeError(
            f"driver {stage}: ids missing from {obs.name}: {missing} "
            "(ledger requeue did not take effect?)")


# ---------------------------------------------------------------------------
# Probe lookup + shared worker plumbing (evidence-only steps 2/3)
# ---------------------------------------------------------------------------

def find_probe(probe_id: str):
    from scripts.run_e1_probe_study import _load_probe_files
    for kf in _load_probe_files(E1):
        for probe in kf["probes"]:
            if probe["probe_id"] == probe_id:
                return kf, probe
    raise KeyError(probe_id)


def save_run(outdir: Path, name: str, result, timed_out, wall_ms, so, se):
    (outdir / f"{name}.json").write_text(
        json.dumps({"result": result, "timed_out": timed_out,
                    "wall_ms": round(wall_ms, 1)}, indent=2),
        encoding="utf-8")
    if (result is None) or (se or "").strip():
        (outdir / f"{name}.stdio.log").write_text(
            f"STDOUT:\n{so}\n\nSTDERR:\n{se}\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Step 2: flip-candidate #7 review (evidence only, never writes the ledger)
# ---------------------------------------------------------------------------

def _si1_verdict(result, timed_out) -> str:
    if timed_out:
        return "whole_probe_timeout"
    if result is None:
        return "worker_crash_no_result"
    div = result.get("divergence")
    if div:
        if (div.get("policy") == "mixed_extremes"
                and div.get("sub_index") == 1):
            return f"si1_{div.get('detail', 'divergence')}"
        return (f"other_divergence({div.get('policy')}/"
                f"{div.get('sub_index')}/{div.get('detail')})")
    for p in result.get("tested_policies", []):
        if (p.get("name") == "mixed_extremes" and p.get("sub_index") == 1
                and p.get("status")):
            return f"si1_{p['status']}"
    vs = result.get("validation_status")
    return "completed_ok" if vs == "pass" else f"status_{vs}"


def step2_review_p46() -> None:
    probe_id = "L1_P46__index_replace__5"
    outdir = REVIEW / "p46_index_replace_5"
    summary_path = outdir / "review_summary.json"
    if summary_path.exists():
        log("step2: review_summary.json already present, skipping")
        return
    from scripts.run_e1_probe_study import (BASELINE_PROTOCOL,
                                            _resolve_problem_file,
                                            run_worker)
    kf, probe = find_probe(probe_id)
    pf = _resolve_problem_file(MK / "KernelBench",
                               kf["kernel"]["level"],
                               kf["kernel"]["problem_id"])
    base_cfg = {
        "mode": "equiv",
        "mutant_id": probe_id,
        "problem_file": str(pf),
        "kernel_code": kf["kernel_source"],
        "mutated_code": probe["mutated_code"],
        "operator_name": probe["operator_name"],
        "device": BASELINE_PROTOCOL["device"],
        # stress seed = base_seed + equiv_runs + si (policy-list independent)
        # -> 0 random rounds, stress seeds 50040/50041/50042 exactly as the
        # production witness (FALSIFY_BASE_SEED 50000 + 40 random rounds).
        "equiv_runs": 0,
        "base_seed": 50040,
        "stress_policies": ["mixed_extremes"],
        "stress_repeats": 3,
        "atol": BASELINE_PROTOCOL["atol"],
        "rtol": BASELINE_PROTOCOL["rtol"],
        "round_timeout": 300,
    }
    log(f"step2: review cfg ready (round_timeout=300, seeds 50040-50042, "
        f"witness sub_index=1/seed=50041); 3x candidate + 1x control")
    if DRY:
        return
    outdir.mkdir(parents=True, exist_ok=True)
    scratch = outdir / "scratch"
    scratch.mkdir(exist_ok=True)

    verdicts = []
    for rep in (1, 2, 3):
        result, timed_out, wall_ms, so, se = run_worker(
            dict(base_cfg), 3600, scratch)
        save_run(outdir, f"candidate_rep{rep}", result, timed_out, wall_ms,
                 so, se)
        v = _si1_verdict(result, timed_out)
        verdicts.append(v)
        log(f"step2: candidate rep{rep}: {v} (wall {wall_ms / 1000:.0f}s)")

    ctrl_cfg = dict(base_cfg,
                    mutant_id=probe_id + "__ORIGINAL_CONTROL",
                    mutated_code=kf["kernel_source"])
    result, timed_out, wall_ms, so, se = run_worker(ctrl_cfg, 3600, scratch)
    save_run(outdir, "control", result, timed_out, wall_ms, so, se)
    ctrl_v = _si1_verdict(result, timed_out)
    log(f"step2: control: {ctrl_v} (wall {wall_ms / 1000:.0f}s)")

    stable = len(set(verdicts)) == 1
    ctrl_ok = ctrl_v == "completed_ok"
    if stable and verdicts[0].startswith("si1_") and ctrl_ok:
        rec = ("MAINTAIN FALSIFIED: candidate deterministically fails round "
               "mixed_extremes/sub1/seed50041 under the relaxed 300s round "
               f"watchdog (3/3 reps: {verdicts[0]}) while the unmutated "
               "control completes the same rounds; witness upgraded to a "
               "reproducible record (candidate_rep*.json).")
    elif stable and verdicts[0] == "completed_ok":
        rec = ("DOWNGRADE the witness round as environment-voided: candidate "
               "completed all mixed_extremes rounds (incl. seed 50041) with "
               "matching outputs under the 300s watchdog (3/3 reps); regrade "
               "the probe from its remaining evidence.")
    else:
        rec = (f"UNSTABLE/UNCLEAR (reps={verdicts}, control={ctrl_v}): "
               "needs human review of the evidence files.")
    rec += (" -- ADVISORY ONLY: the main ledger was NOT modified; human "
            "confirmation decides the final grade.")
    summary = {
        "probe_id": probe_id,
        "witness": {"policy": "mixed_extremes", "sub_index": 1,
                    "seed": 50041, "original_detail": "candidate_crash",
                    "original_cause": "90s round-watchdog timeout"},
        "protocol": {"round_timeout_s": 300, "equiv_runs": 0,
                     "base_seed": 50040,
                     "stress_policies": ["mixed_extremes"],
                     "stress_repeats": 3, "candidate_reps": 3,
                     "control_reps": 1, "worker_timeout_s": 3600,
                     "gpu_memory_fraction": 0.92},
        "candidate_verdicts": verdicts,
        "control_verdict": ctrl_v,
        "recommendation": rec,
        "finished_at": datetime.now().isoformat(),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (outdir / "RECOMMENDATION.txt").write_text(rec + "\n", encoding="utf-8")
    log(f"step2: RECOMMENDATION: {rec}")


# ---------------------------------------------------------------------------
# Step 3: L1_P95__relop_replace__5 equiv crash retry (evidence only)
# ---------------------------------------------------------------------------

def step3_retry_p95() -> None:
    probe_id = "L1_P95__relop_replace__5"
    outdir = REVIEW / "p95_relop_replace_5"
    summary_path = outdir / "retry_summary.json"
    if summary_path.exists():
        log("step3: retry_summary.json already present, skipping")
        return
    from scripts.run_e1_probe_study import (BASELINE_PROTOCOL,
                                            EQUIV_BASE_SEED,
                                            EQUIV_ROUND_TIMEOUT_S,
                                            EQUIV_RUNS,
                                            _resolve_problem_file,
                                            grade_equiv_evidence,
                                            run_worker)
    kf, probe = find_probe(probe_id)
    pf = _resolve_problem_file(MK / "KernelBench",
                               kf["kernel"]["level"],
                               kf["kernel"]["problem_id"])
    cfg = {
        "mode": "equiv",
        "mutant_id": probe_id,
        "problem_file": str(pf),
        "kernel_code": kf["kernel_source"],
        "mutated_code": probe["mutated_code"],
        "operator_name": probe["operator_name"],
        "device": BASELINE_PROTOCOL["device"],
        "equiv_runs": EQUIV_RUNS,
        "base_seed": EQUIV_BASE_SEED,
        "atol": BASELINE_PROTOCOL["atol"],
        "rtol": BASELINE_PROTOCOL["rtol"],
        "round_timeout": EQUIV_ROUND_TIMEOUT_S,
    }
    log(f"step3: retry cfg mirrors the equiv protocol (equiv_runs="
        f"{EQUIV_RUNS}, base_seed={EQUIV_BASE_SEED}, round_timeout="
        f"{EQUIV_ROUND_TIMEOUT_S}s); 1x candidate + 1x control")
    if DRY:
        return
    outdir.mkdir(parents=True, exist_ok=True)
    scratch = outdir / "scratch"
    scratch.mkdir(exist_ok=True)

    result, timed_out, wall_ms, so, se = run_worker(dict(cfg), 3600, scratch)
    save_run(outdir, "candidate", result, timed_out, wall_ms, so, se)
    vstatus, grade, partial = grade_equiv_evidence(result, timed_out)
    reason = ((result or {}).get("reason") or (result or {}).get("error")
              or (se or ""))[:300]
    log(f"step3: candidate -> grade={grade} status={vstatus} "
        f"wall={wall_ms / 1000:.0f}s reason={reason[:120]!r}")

    ctrl_cfg = dict(cfg, mutant_id=probe_id + "__ORIGINAL_CONTROL",
                    mutated_code=kf["kernel_source"])
    cresult, ctimed_out, cwall_ms, cso, cse_ = run_worker(
        ctrl_cfg, 3600, scratch)
    save_run(outdir, "control", cresult, ctimed_out, cwall_ms, cso, cse_)
    ctrl_ok = (cresult or {}).get("validation_status") == "pass"
    log(f"step3: control -> healthy={ctrl_ok} wall={cwall_ms / 1000:.0f}s")

    crash_like = grade == "INCONCLUSIVE" and (
        result is None or "memory access" in reason or "CUDA" in reason)
    if crash_like and ctrl_ok:
        rec = ("Crash REPRODUCED with a healthy unmutated reference on the "
               "same protocol: propose SPEC_VIOLATION under the strict "
               "oracle (mutant-induced illegal memory access).")
    elif grade != "INCONCLUSIVE":
        rec = (f"Retry graded {grade} (crash did not reproduce): propose "
               "recording this grade through the normal pipeline; the "
               "original crash was an environment transient.")
    else:
        rec = (f"Retry still INCONCLUSIVE (grade={grade}, control_healthy="
               f"{ctrl_ok}): needs human review; per the settlement rules a "
               "second failed retry would place it in the final "
               "INCONCLUSIVE column.")
    rec += (" -- ADVISORY ONLY: the main ledger was NOT modified; human "
            "confirmation decides the final grade.")
    summary = {
        "probe_id": probe_id,
        "original": {"grade": "INCONCLUSIVE",
                     "reason": "CUDA illegal memory access, wall 61s",
                     "finished_at": "2026-07-24T08:01:16Z"},
        "protocol": {"equiv_runs": EQUIV_RUNS, "base_seed": EQUIV_BASE_SEED,
                     "round_timeout_s": EQUIV_ROUND_TIMEOUT_S,
                     "worker_timeout_s": 3600,
                     "gpu_memory_fraction": 0.92},
        "candidate": {"grade": grade, "validation_status": vstatus,
                      "wall_ms": round(wall_ms, 1), "reason": reason},
        "control_healthy": ctrl_ok,
        "recommendation": rec,
        "finished_at": datetime.now().isoformat(),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (outdir / "RECOMMENDATION.txt").write_text(rec + "\n", encoding="utf-8")
    log(f"step3: RECOMMENDATION: {rec}")


# ---------------------------------------------------------------------------

def main() -> int:
    os.environ["PATH"] = ("/usr/local/cuda/bin:/root/miniconda3/bin:"
                          "/usr/local/bin:/usr/bin:/bin")
    os.environ["TORCH_EXTENSIONS_DIR"] = str(RUNS / "torch_ext")
    os.environ["MK_GPU_MEMORY_FRACTION"] = "0.92"
    os.chdir(MK)
    sys.path.insert(0, str(MK))

    log("=== final-window orchestrator start ===")
    if DONE.exists():
        log("FINAL_WINDOW_DONE already exists - nothing to do")
        return 0

    step0_preconditions()

    for stage, lane, tag, timeout, ids in STAGES:
        log(f"--- stage {stage}: lane{lane} tag={tag} timeout={timeout}s "
            f"({len(ids)} probe[s]) ---")
        requeue_ledger(lane, ids)
        run_requeue_driver(stage, lane, tag, timeout, ids)

    log("--- stage 2: flip-candidate #7 review (evidence only) ---")
    step2_review_p46()
    log("--- stage 3: P95 equiv crash retry (evidence only) ---")
    step3_retry_p95()

    if not DRY:
        DONE.write_text(json.dumps({
            "finished_at": datetime.now().isoformat(),
            "stages": [s[0] for s in STAGES] + ["p46_review", "p95_retry"],
            "note": ("requeue observations live in tagged "
                     "cse_observations_lane{3,5}_* files; review/retry "
                     "evidence under e1/final_window_review/ awaits human "
                     "adjudication (ledger untouched)"),
        }, indent=2), encoding="utf-8")
        log("FINAL_WINDOW_DONE written")
    log("=== final-window orchestrator complete ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log("FATAL:\n" + traceback.format_exc())
        sys.exit(1)
