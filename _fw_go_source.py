#!/usr/bin/env python3
"""E1 final exclusive-window settlement orchestrator (2026-07-29).

Fired exactly once by _final_window_trigger.sh after lane3's DONE marker
file exists.  Serial, single-driver, whole-GPU steps:

  0. preconditions: lane3 driver really exited, guard exited (all lane
     markers present -> guard writes CSE_DONE and exits on its own).
  1/2. ledger requeue + reruns, staged so each rerun batch gets its own
     budget (ids are only removed from a lane's completed checkpoint right
     before the driver invocation that re-runs them):
       2a  L1_P96__launch_config_mutate__0        lane3  --timeout 5400  tag p96_5400
       2b  3x L1_P53 + L1_P52__arith_replace__11
           + L1_P46__relop_replace__5             lane3  --timeout 3600  tag final_requeue
       2c  L1_P23__mask_boundary__1               lane5  --timeout 3600  tag final_requeue
     Original INCONCLUSIVE observation lines are moved verbatim into
     cse_observations_inc_archive_v2.jsonl (never deleted); the ids are
     dropped from cse_completed_lane{3,5}.json (with .bak backups).  The
     re-run drivers write their own cse_observations_lane*_<tag>.jsonl
     (glob-compatible with the campaign merge; grading semantics untouched;
     cse_policy_skip.json auto-applies to P53).
  3. #7 review, EVIDENCE ONLY (no ledger writes): L1_P46__index_replace__5
     witness round (mixed_extremes / sub 1 / seed 50041, original
     candidate_crash = 90s round-watchdog timeout) re-run with a 300s round
     watchdog: 3 candidate reps (stress seeds 50040/50041/50042, bit-equal
     to production: seed = base_seed + equiv_runs + si, policy-list
     independent) + 1 unmutated control.  Writes recommendation only.
  3b. P37 5/5-cluster review, EVIDENCE ONLY (added 2026-07-30 before
     arming fired): unmutated-control self-stability x3 + extreme-pair flip
     reproduction (sync_remove__0 / epsilon_modify__0) x3, all on the
     witness round boundary_last_element/sub0/seed 50040; H1 (independent
     defects) vs H2 (kernel-level numeric sensitivity) recommendation only.
  4. L1_P95__relop_replace__5 equiv crash retry, EVIDENCE ONLY: one
     candidate re-run mirroring the equiv-phase cfg + 1 unmutated control.
     Writes recommendation only.
  5. FINAL_WINDOW_DONE marker + final_window_summary.json.

--dry-run: walks every step, logs exactly what would happen (read-only
checks included), launches nothing, edits nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

MK = Path("/root/mk_v2")
RUNS = Path("/root/mk_v2_runs")
E1 = RUNS / "e1"
PY = "/root/miniconda3/bin/python"
LOG_PATH = RUNS / "final_window.log"
LANE3_MARK = E1 / "CSE_DONE_LANE3"
DONE_MARK = E1 / "FINAL_WINDOW_DONE"
GUARD_PIDFILE = RUNS / "e1_guard.pid"
LOCK_DIR = RUNS / "final_window.lock"
ARCHIVE = E1 / "cse_observations_inc_archive_v2.jsonl"
REVIEW = E1 / "final_window_review"
SUMMARY_PATH = E1 / "final_window_summary.json"
BAK_SUFFIX = ".bak_final_window"

REQUEUE_2A = ["L1_P96__launch_config_mutate__0"]
REQUEUE_2B = [
    "L1_P53__arith_replace__17",
    "L1_P53__relop_replace__4",
    "L1_P53__const_perturb__0",
    "L1_P52__arith_replace__11",
    "L1_P46__relop_replace__5",
]
REQUEUE_2C = ["L1_P23__mask_boundary__1"]

REVIEW_P46 = "L1_P46__index_replace__5"
REVIEW_P95 = "L1_P95__relop_replace__5"
# P37 5/5 cluster (round 74 = boundary_last_element/sub0/seed 50040, all five
# LIKELY probes flipped with "exactly 1 value over tolerance"): H1 true
# positives vs H2 kernel-level numeric sensitivity.  Review = unmutated
# control x3 + the extreme pair (max/min max_abs_error) x3 reproductions.
REVIEW_P37_CANDS = [
    ("L1_P37__sync_remove__0", 0.182176),     # largest max_abs_error
    ("L1_P37__epsilon_modify__0", 0.0352935), # smallest max_abs_error
]

DRY = False
SUMMARY = {"started_at": None, "dry_run": None, "steps": {}}


def log(msg):
    line = f"[final-window {datetime.now().strftime('%F %T %z')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def sh(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def obs_path(lane):
    return E1 / f"cse_observations_lane{lane}.jsonl"


def completed_path(lane):
    return E1 / f"cse_completed_lane{lane}.json"


def atomic_write(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".fw_tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Step 0: preconditions
# ---------------------------------------------------------------------------

def lane3_driver_pids():
    rc, out, _ = sh("pgrep -f 'run_e1_cse_falsify.py.*--lane 3$' || true")
    return [int(x) for x in out.split()] if out else []


def guard_alive():
    if not GUARD_PIDFILE.exists():
        return None
    try:
        pid = int(GUARD_PIDFILE.read_text().strip())
    except ValueError:
        return None
    rc, _, _ = sh(f"kill -0 {pid} 2>/dev/null")
    return pid if rc == 0 else None


def step0_preconditions():
    t0 = time.time()
    log(f"STEP0 preconditions (dry_run={DRY})")
    mark_ok = LANE3_MARK.exists()
    log(f"  lane3 DONE marker {LANE3_MARK}: {'present' if mark_ok else 'MISSING'}")
    if not mark_ok and not DRY:
        log("  ABORT: marker missing (trigger should not have fired)")
        sys.exit(2)

    pids = lane3_driver_pids()
    if pids and not DRY:
        log(f"  lane3 driver still up ({pids}); waiting up to 1800s for clean exit")
        deadline = time.time() + 1800
        while pids and time.time() < deadline:
            time.sleep(15)
            pids = lane3_driver_pids()
        if pids:
            log(f"  ABORT: lane3 driver {pids} did not exit; refusing to touch ledger")
            sys.exit(2)
    log(f"  lane3 driver processes: {pids or 'none'}")

    gpid = guard_alive()
    if gpid and not DRY:
        log(f"  guard still alive (pid {gpid}); all lane markers present -> it "
            "writes CSE_DONE and exits within one 120s cycle; waiting up to 900s")
        deadline = time.time() + 900
        while gpid and time.time() < deadline:
            time.sleep(20)
            gpid = guard_alive()
        if gpid:
            log(f"  WARN: guard pid {gpid} still alive after wait; safe to proceed "
                "(lane3 marker blocks any AUTORESTART; tagged drivers do not match "
                "its pgrep pattern '--lane N$'), continuing")
    log(f"  guard: {'alive pid ' + str(gpid) if gpid else 'exited'}")

    rc, out, _ = sh("pgrep -f 'e1_sentinel.py' || true")
    log(f"  sentinel pids: {out or 'NONE (warn: expected on duty)'}")
    rc, out, _ = sh("nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader")
    log(f"  gpu memory: {out}")
    SUMMARY["steps"]["step0"] = {"elapsed_s": round(time.time() - t0, 1),
                                 "marker": mark_ok, "guard_pid_left": gpid}


# ---------------------------------------------------------------------------
# Ledger requeue (backup + archive + drop ids), idempotent per id
# ---------------------------------------------------------------------------

def backup_once(path: Path):
    bak = path.with_name(path.name + BAK_SUFFIX)
    if bak.exists():
        log(f"  backup already exists: {bak.name}")
        return
    if DRY:
        log(f"  [dry-run] would back up {path.name} -> {bak.name}")
        return
    shutil.copy2(path, bak)
    log(f"  backed up {path.name} -> {bak.name} ({path.stat().st_size} bytes)")


def requeue_ids(lane: int, ids: list):
    """Archive the ids' INCONCLUSIVE obs lines + drop them from completed."""
    op, cp = obs_path(lane), completed_path(lane)
    lines = op.read_text(encoding="utf-8").splitlines()
    keep, move = [], []
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            keep.append(line)
            continue
        if rec.get("probe_id") in ids and rec.get("outcome") == "INCONCLUSIVE":
            move.append(line)
        else:
            keep.append(line)
    completed = json.loads(cp.read_text(encoding="utf-8"))
    present = [i for i in ids if i in completed]
    log(f"  lane{lane}: {len(move)} INCONCLUSIVE obs line(s) to archive, "
        f"{len(present)}/{len(ids)} id(s) present in completed")
    moved_ids = sorted({json.loads(l)['probe_id'] for l in move})
    log(f"  obs lines to move: {moved_ids}")
    already = [i for i in ids if i not in completed and i not in moved_ids]
    if already:
        log(f"  already requeued earlier (idempotent skip): {already}")
    if DRY:
        log(f"  [dry-run] would append {len(move)} line(s) to {ARCHIVE.name}, "
            f"rewrite {op.name} ({len(lines)}->{len(keep)} lines), drop "
            f"{present} from {cp.name} ({len(completed)}->{len(completed)-len(present)})")
        return
    if move:
        with open(ARCHIVE, "a", encoding="utf-8") as fh:
            for line in move:
                fh.write(line + "\n")
        atomic_write(op, "\n".join(keep) + ("\n" if keep else ""))
        log(f"  archived {len(move)} line(s) -> {ARCHIVE.name}; "
            f"{op.name} now {len(keep)} lines")
    if present:
        remaining = [i for i in completed if i not in ids]
        atomic_write(cp, json.dumps(sorted(remaining)))
        log(f"  {cp.name}: {len(completed)} -> {len(remaining)} ids")


# ---------------------------------------------------------------------------
# Requeue driver runs
# ---------------------------------------------------------------------------

def driver_env():
    env = os.environ.copy()
    env["PATH"] = "/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin"
    env["TORCH_EXTENSIONS_DIR"] = str(RUNS / "torch_ext")
    env["MK_GPU_MEMORY_FRACTION"] = "0.92"
    return env


def run_requeue_driver(step: str, lane: int, tag: str, timeout: int, expect_ids: list):
    cmd = [PY, "-u", "scripts/run_e1_cse_falsify.py",
           "--out-dir", str(E1), "--kernelbench-root", "KernelBench",
           "--timeout", str(timeout),
           "--lane-plan", str(E1 / "cse_lane_plan.json"),
           "--lane", str(lane), "--lane-tag", tag]
    dlog = RUNS / f"e1_cse_lane{lane}_{tag}.log"
    log(f"  {step}: driver lane={lane} tag={tag} timeout={timeout}s "
        f"frac=0.92 log={dlog.name}")
    log(f"  {step}: cmd: {' '.join(cmd)}")
    if DRY:
        log(f"  [dry-run] would run serially and wait; expected reruns: {expect_ids}")
        return {"dry_run": True}
    t0 = time.time()
    with open(dlog, "ab") as fh:
        rc = subprocess.call(cmd, cwd=str(MK), env=driver_env(),
                             stdout=fh, stderr=fh)
    elapsed = round(time.time() - t0, 1)
    tagged_obs = E1 / f"cse_observations_lane{lane}_{tag}.jsonl"
    outcomes = {}
    if tagged_obs.exists():
        for line in tagged_obs.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                outcomes[r["probe_id"]] = r.get("outcome")
    log(f"  {step}: driver exit={rc} elapsed={elapsed}s outcomes={outcomes}")
    missing = [i for i in expect_ids if i not in outcomes]
    inc = [i for i, o in outcomes.items() if o == "INCONCLUSIVE"]
    if rc != 0 or missing:
        log(f"  {step}: WARN driver rc={rc}, missing={missing} "
            "(left for human review; not retried automatically)")
    if inc:
        log(f"  {step}: WARN still INCONCLUSIVE after exclusive-window rerun: {inc} "
            "(left for human review)")
    return {"exit": rc, "elapsed_s": elapsed, "outcomes": outcomes,
            "missing": missing, "still_inconclusive": inc}


def step12_requeues():
    log("STEP1/2 ledger requeue + exclusive-window reruns")
    t0 = time.time()
    for p in (obs_path(3), completed_path(3), obs_path(5), completed_path(5)):
        backup_once(p)
    res = {}
    log(" step2a: P96 near-miss timeout -> 5400s budget")
    requeue_ids(3, REQUEUE_2A)
    res["2a"] = run_requeue_driver("step2a", 3, "p96_5400", 5400, REQUEUE_2A)
    log(" step2b: 3x P53 (policy-skip applies) + P52/P46 transient-OOM family -> 3600s")
    requeue_ids(3, REQUEUE_2B)
    res["2b"] = run_requeue_driver("step2b", 3, "final_requeue", 3600, REQUEUE_2B)
    log(" step2c: lane5 P23 transient-OOM -> 3600s")
    requeue_ids(5, REQUEUE_2C)
    res["2c"] = run_requeue_driver("step2c", 5, "final_requeue", 3600, REQUEUE_2C)
    res["elapsed_s"] = round(time.time() - t0, 1)
    SUMMARY["steps"]["step12"] = res


# ---------------------------------------------------------------------------
# Evidence-only reviews (steps 3/4).  NO ledger writes here, by design.
# ---------------------------------------------------------------------------

_PS = None
_FAL = None


def helpers():
    global _PS, _FAL
    if _PS is None:
        sys.path.insert(0, str(MK))
        import scripts.run_e1_probe_study as ps
        import scripts.run_e1_cse_falsify as fal
        _PS, _FAL = ps, fal
    return _PS, _FAL


_PROBE_FILES = None


def probe_files():
    global _PROBE_FILES
    if _PROBE_FILES is None:
        ps, _ = helpers()
        _PROBE_FILES = ps._load_probe_files(E1)
    return _PROBE_FILES


def find_probe(probe_id):
    for kf in probe_files():
        for probe in kf["probes"]:
            if probe["probe_id"] == probe_id:
                return kf, probe
    raise KeyError(f"probe {probe_id} not found under {E1}/probes")


def base_cfg(kf, probe, mutant_id, mutated_code):
    ps, _ = helpers()
    problem_file = ps._resolve_problem_file(
        MK / "KernelBench", kf["kernel"]["level"], kf["kernel"]["problem_id"])
    return {
        "mode": "equiv",
        "mutant_id": mutant_id,
        "problem_file": str(problem_file),
        "kernel_code": kf["kernel_source"],
        "mutated_code": mutated_code,
        "operator_name": probe["operator_name"],
        "device": ps.BASELINE_PROTOCOL["device"],
        "atol": ps.BASELINE_PROTOCOL["atol"],
        "rtol": ps.BASELINE_PROTOCOL["rtol"],
    }


def run_review_worker(subdir: Path, name: str, cfg: dict, timeout: int):
    ps, _ = helpers()
    scratch = subdir / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    log(f"    worker {name}: timeout={timeout}s round_timeout={cfg.get('round_timeout')}s")
    result, timed_out, wall_ms, so, se = ps.run_worker(cfg, timeout, scratch)
    (subdir / f"{name}_result.json").write_text(
        json.dumps({"cfg_digest": {k: cfg[k] for k in
                                   ("mutant_id", "equiv_runs", "base_seed",
                                    "stress_policies", "stress_repeats",
                                    "round_timeout") if k in cfg},
                    "timed_out": timed_out, "wall_ms": round(wall_ms, 1),
                    "result": result}, indent=2, default=str),
        encoding="utf-8")
    if se.strip() or result is None:
        (subdir / f"{name}_worker.log").write_text(
            f"STDOUT:\n{so}\n\nSTDERR:\n{se}\n", encoding="utf-8")
    vs = (result or {}).get("validation_status")
    log(f"    worker {name}: timed_out={timed_out} wall={round(wall_ms/1000,1)}s "
        f"validation_status={vs} round_timeouts={(result or {}).get('round_timeouts')} "
        f"divergence={'yes' if (result or {}).get('divergence') else 'no'}")
    return result, timed_out


def p46_rep_verdict(result, timed_out):
    if timed_out or result is None:
        return "worker_failure"
    if result.get("validation_status") == "pass":
        return "pass"
    div = result.get("divergence")
    if div:
        phases = {e.get("phase") for e in (div.get("errors") or [])}
        if "candidate" in phases or div.get("detail") == "candidate_crash":
            return "candidate_reproduced"
        return "diverged_other"
    if result.get("round_timeouts", 0) > 0:
        return "round_timeout_no_witness"
    return "inconclusive_other"


def step3_review_p46():
    log("STEP3 #7 targeted review (EVIDENCE ONLY, ledger untouched): "
        f"{REVIEW_P46}, witness round mixed_extremes/sub1/seed 50041, "
        "round watchdog relaxed 90s -> 300s")
    t0 = time.time()
    sub = REVIEW / "p46_index_replace_5"
    summary_file = sub / "review_summary.json"
    if summary_file.exists():
        log("  review summary already exists; skipping (idempotent)")
        SUMMARY["steps"]["step3"] = {"skipped": "already done"}
        return
    ps, fal = helpers()
    kf, probe = find_probe(REVIEW_P46)
    stress_base = fal.FALSIFY_BASE_SEED + fal.FALSIFY_EQUIV_RUNS  # 50040
    common = {
        "equiv_runs": 0,           # skip random rounds; stress seeds =
        "base_seed": stress_base,  # base+0+si = 50040/50041/50042, exactly
        "stress_policies": ["mixed_extremes"],   # the production seeds (seed
        "stress_repeats": 3,       # derivation is policy-list independent)
        "round_timeout": 300,
    }
    log(f"  stress seeds will be {stress_base}+si (si=0,1,2); witness si=1 seed "
        f"{stress_base + 1}")
    if DRY:
        log("  [dry-run] would run 3 candidate reps + 1 unmutated control, "
            f"outputs under {sub}")
        SUMMARY["steps"]["step3"] = {"dry_run": True}
        return
    sub.mkdir(parents=True, exist_ok=True)
    verdicts = []
    for rep in range(1, 4):
        cfg = dict(base_cfg(kf, probe, REVIEW_P46, probe["mutated_code"]), **common)
        result, timed_out = run_review_worker(sub, f"candidate_rep{rep}", cfg, 3600)
        verdicts.append(p46_rep_verdict(result, timed_out))
    ctl_cfg = dict(base_cfg(kf, probe, REVIEW_P46 + "__CONTROL",
                            kf["kernel_source"]), **common)
    ctl_result, ctl_to = run_review_worker(sub, "control", ctl_cfg, 3600)
    ctl_verdict = p46_rep_verdict(ctl_result, ctl_to)

    if all(v == "candidate_reproduced" for v in verdicts) and ctl_verdict == "pass":
        rec = ("维持 FALSIFIED:candidate 在 300s 轮级看门狗下 3/3 次稳定超时/崩溃,"
               "而未变异对照(原内核 vs 参考)同轮 3 轮全部正常完成;witness 升级为可复现"
               "记录(300s 下仍不可完成)。请人工确认后更新 witness 备注,主账判级不变。")
        code = "MAINTAIN_FALSIFIED_WITNESS_REPRODUCIBLE"
    elif all(v == "pass" for v in verdicts):
        rec = ("降级建议:candidate 在 300s 内 3/3 次正常完成且输出一致,原 90s "
               "candidate_crash 判为环境作废(看门狗过紧);该探针需按剩余证据重新判级。"
               "请人工确认后执行改账。")
        code = "DOWNGRADE_ROUND_ENV_VOID"
    else:
        rec = (f"结果不稳定(candidate 3 次判定={verdicts}, control={ctl_verdict}),"
               "不满足两侧任一判据,请人工逐份复核证据文件。")
        code = "UNSTABLE_HUMAN_REVIEW"
    summary = {
        "probe_id": REVIEW_P46,
        "witness": {"policy": "mixed_extremes", "sub_index": 1, "seed": 50041,
                    "original_detail": "candidate_crash (= 90s round watchdog)"},
        "protocol": dict(common),
        "candidate_verdicts": verdicts,
        "control_verdict": ctl_verdict,
        "recommendation_code": code,
        "recommendation": rec,
        "ledger_written": False,
        "finished_at": datetime.now().isoformat(),
    }
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    (sub / "RECOMMENDATION.txt").write_text(rec + "\n", encoding="utf-8")
    log(f"  STEP3 verdicts: candidate={verdicts} control={ctl_verdict} -> {code}")
    log("  STEP3 主账未改;定级决定留给人工确认")
    summary["elapsed_s"] = round(time.time() - t0, 1)
    SUMMARY["steps"]["step3"] = summary


def extract_max_abs_error(result):
    div = (result or {}).get("divergence") or {}
    for mm in ((div.get("oracle") or {}).get("mismatches") or []):
        m = re.search(r"max_abs_error=([0-9.eE+-]+)", mm.get("message", ""))
        if m:
            return float(m.group(1))
    return None


def p37_run_verdict(result, timed_out):
    """One boundary_last_element/seed-50040 round: pass / diverged / other."""
    if timed_out or result is None:
        return "worker_failure", None
    if result.get("validation_status") == "pass":
        return "pass", None
    if result.get("divergence"):
        return "diverged", extract_max_abs_error(result)
    return "other", None


def step3b_review_p37():
    log("STEP3b P37 5/5-cluster review (EVIDENCE ONLY, ledger untouched): "
        "round 74 = boundary_last_element/sub0/seed 50040, all 5 LIKELY "
        "probes flipped with exactly-1-value oracle fails "
        "(max_abs_error 0.035-0.182 vs tol 0.01); H1 independent true "
        "positives vs H2 kernel-level reduction-order sensitivity")
    t0 = time.time()
    sub = REVIEW / "p37_cluster"
    summary_file = sub / "review_summary.json"
    if summary_file.exists():
        log("  review summary already exists; skipping (idempotent)")
        SUMMARY["steps"]["step3b"] = {"skipped": "already done"}
        return
    ps, fal = helpers()
    kf, probe0 = find_probe(REVIEW_P37_CANDS[0][0])
    stress_base = fal.FALSIFY_BASE_SEED + fal.FALSIFY_EQUIV_RUNS  # 50040
    common = {
        "equiv_runs": 0,            # stress seed = base+0+si = 50040 (si=0),
        "base_seed": stress_base,   # exactly the production witness seed;
        "stress_policies": ["boundary_last_element"],  # policy-list
        "stress_repeats": 1,        # independent derivation (see step3)
        "round_timeout": 90,        # production value; round is fast, the
    }                               # original fails were numeric, not timeout
    log(f"  protocol: unmutated control x3 + 2 candidates x3 reps, each an "
        f"independent worker process/CUDA context; seed {stress_base}, "
        "input 112x64x512x512 last-element=1e4")
    if DRY:
        log("  [dry-run] would run control x3 + "
            f"{[c[0] for c in REVIEW_P37_CANDS]} x3 reps each, outputs under {sub}")
        SUMMARY["steps"]["step3b"] = {"dry_run": True}
        return
    sub.mkdir(parents=True, exist_ok=True)

    # 1) unmutated-control self-stability: original P37 kernel as candidate
    #    vs reference, 3 independent processes.  Any over-tolerance diff here
    #    is mutation-independent (H2 signal).
    ctl_verdicts, ctl_errs = [], []
    for rep in range(1, 4):
        cfg = dict(base_cfg(kf, probe0, "L1_P37__ORIGINAL_CONTROL",
                            kf["kernel_source"]), **common)
        result, timed_out = run_review_worker(sub, f"control_rep{rep}", cfg, 3600)
        v, err = p37_run_verdict(result, timed_out)
        ctl_verdicts.append(v)
        ctl_errs.append(err)
    log(f"  control verdicts={ctl_verdicts} max_abs_errors={ctl_errs}")

    # 2) flip reproduction on the extreme pair (largest/smallest error)
    cand_out = {}
    for probe_id, orig_err in REVIEW_P37_CANDS:
        ckf, cprobe = find_probe(probe_id)
        verdicts, errs = [], []
        for rep in range(1, 4):
            cfg = dict(base_cfg(ckf, cprobe, probe_id,
                                cprobe["mutated_code"]), **common)
            result, timed_out = run_review_worker(
                sub, f"{probe_id}_rep{rep}", cfg, 3600)
            v, err = p37_run_verdict(result, timed_out)
            verdicts.append(v)
            errs.append(err)
        cand_out[probe_id] = {"original_max_abs_error": orig_err,
                              "verdicts": verdicts, "max_abs_errors": errs}
        log(f"  {probe_id}: verdicts={verdicts} errors={errs} "
            f"(original {orig_err})")

    ctl_diverged = any(v == "diverged" for v in ctl_verdicts)
    all_cand_repro = all(all(v == "diverged" for v in c["verdicts"])
                         for c in cand_out.values())
    all_cand_pass = all(all(v == "pass" for v in c["verdicts"])
                        for c in cand_out.values())
    if ctl_diverged:
        rec = ("支持 H2(内核级数值敏感):未变异 P37 原内核在同款 "
               "boundary_last_element/seed 50040 输入下,candidate 编译路径 vs 参考"
               f"路径自身即超差(3 遍判定={ctl_verdicts},误差={ctl_errs})。"
               "5 条同轮位翻案疑为同一『内核 × 末元素极值 × 归约顺序』交互的重复观测,"
               "建议人工按 H2 处理(该轮对 P37 家族的 witness 作废/降权,按剩余证据"
               "重新判级,或以更稳健 oracle 复核)。不改主账。")
        code = "H2_KERNEL_NUMERIC_SENSITIVITY"
    elif all(v == "pass" for v in ctl_verdicts) and all_cand_repro:
        rec = ("支持 H1(真阳性):未变异对照 3/3 在容差内通过,而两条抽检变异体 "
               "3/3 稳定复现单值超差(误差见 review_summary,含与原 witness 的对照)。"
               "边界定向策略命中的是变异引入的真实缺陷,建议维持 5 条 FALSIFIED,"
               "witness 升级为可复现记录。人工确认后入账。")
        code = "H1_TRUE_POSITIVES_REPRODUCIBLE"
    elif all(v == "pass" for v in ctl_verdicts) and all_cand_pass:
        rec = ("异常:对照通过且两条变异体复现也全部通过(翻案未复现),原 witness "
               "疑为瞬态,请人工核对本次与原轮环境差异后决定是否对 5 条全量复现。")
        code = "FLIP_NOT_REPRODUCED_HUMAN_REVIEW"
    else:
        rec = (f"结果混合(control={ctl_verdicts}, candidates="
               f"{ {k: v['verdicts'] for k, v in cand_out.items()} }),"
               "不满足 H1/H2 任一清晰判据,请人工逐份复核证据文件。")
        code = "MIXED_HUMAN_REVIEW"
    summary = {
        "cluster": "L1_P37 5/5 flip @ round74 boundary_last_element/sub0/seed50040",
        "hypotheses": {"H1": "independent mutation defects",
                       "H2": "kernel-level last-element reduction sensitivity"},
        "protocol": dict(common),
        "control": {"verdicts": ctl_verdicts, "max_abs_errors": ctl_errs},
        "candidates": cand_out,
        "recommendation_code": code,
        "recommendation": rec,
        "ledger_written": False,
        "finished_at": datetime.now().isoformat(),
    }
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    (sub / "RECOMMENDATION.txt").write_text(rec + "\n", encoding="utf-8")
    log(f"  STEP3b -> {code}")
    log("  STEP3b 主账未改;H1/H2 定夺留给人工确认")
    summary["elapsed_s"] = round(time.time() - t0, 1)
    SUMMARY["steps"]["step3b"] = summary


def step4_review_p95():
    log("STEP4 P95 equiv crash retry (EVIDENCE ONLY, ledger untouched): "
        f"{REVIEW_P95}, original: CUDA illegal memory access @61s")
    t0 = time.time()
    sub = REVIEW / "p95_relop_replace_5"
    summary_file = sub / "review_summary.json"
    if summary_file.exists():
        log("  review summary already exists; skipping (idempotent)")
        SUMMARY["steps"]["step4"] = {"skipped": "already done"}
        return
    ps, _ = helpers()
    kf, probe = find_probe(REVIEW_P95)
    common = {
        "equiv_runs": ps.EQUIV_RUNS,          # mirror phase_equiv cfg exactly
        "base_seed": ps.EQUIV_BASE_SEED,
        "round_timeout": ps.EQUIV_ROUND_TIMEOUT_S,
    }
    if DRY:
        log("  [dry-run] would run 1 candidate equiv rerun + 1 unmutated control, "
            f"outputs under {sub}")
        SUMMARY["steps"]["step4"] = {"dry_run": True}
        return
    sub.mkdir(parents=True, exist_ok=True)
    cfg = dict(base_cfg(kf, probe, REVIEW_P95, probe["mutated_code"]), **common)
    result, timed_out = run_review_worker(sub, "candidate", cfg, 1800)
    vs, grade, _ = ps.grade_equiv_evidence(result, timed_out)
    reason = (result or {}).get("reason", "") or ""
    crashed = result is None or "illegal memory access" in reason.lower() \
        or "worker crashed" in reason.lower()
    ctl_cfg = dict(base_cfg(kf, probe, REVIEW_P95 + "__CONTROL",
                            kf["kernel_source"]), **common)
    ctl_result, ctl_to = run_review_worker(sub, "control", ctl_cfg, 1800)
    ctl_vs, ctl_grade, _ = ps.grade_equiv_evidence(ctl_result, ctl_to)

    if crashed and ctl_grade == "LIKELY_EQUIVALENT":
        rec = ("崩溃确定性复现(candidate 再次 CUDA 崩溃/worker 失败)且参考端健康"
               f"(未变异对照判级 {ctl_grade}):按清算表预案,建议按严格 Oracle 处理为 "
               "SPEC_VIOLATION(实锤非等价,越界访问类真实缺陷)。请人工确认后改账。")
        code = "SUGGEST_SPEC_VIOLATION"
    elif crashed:
        rec = (f"candidate 再次崩溃,但对照判级为 {ctl_grade}(参考端不健康或环境异常),"
               "无法归因于变异体,请人工排查环境后再定。")
        code = "CRASH_BUT_CONTROL_UNHEALTHY"
    else:
        rec = (f"瞬态未复现:candidate 本次正常完成,判级建议 = {grade}"
               f"(validation_status={vs})。请人工确认后按本次证据入账。")
        code = f"TRANSIENT_GONE_GRADE_{grade}"
    summary = {
        "probe_id": REVIEW_P95,
        "original": "worker crash: CUDA illegal memory access, wall 61s, equiv phase",
        "protocol": dict(common),
        "candidate": {"grade": grade, "validation_status": vs,
                      "crashed": crashed, "reason_head": reason[:200]},
        "control": {"grade": ctl_grade, "validation_status": ctl_vs},
        "recommendation_code": code,
        "recommendation": rec,
        "ledger_written": False,
        "finished_at": datetime.now().isoformat(),
    }
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    (sub / "RECOMMENDATION.txt").write_text(rec + "\n", encoding="utf-8")
    log(f"  STEP4 candidate grade={grade} crashed={crashed} control={ctl_grade} -> {code}")
    log("  STEP4 主账未改;定级决定留给人工确认")
    summary["elapsed_s"] = round(time.time() - t0, 1)
    SUMMARY["steps"]["step4"] = summary


# ---------------------------------------------------------------------------

def main():
    global DRY
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    DRY = args.dry_run
    SUMMARY["started_at"] = datetime.now().isoformat()
    SUMMARY["dry_run"] = DRY

    if DONE_MARK.exists():
        log(f"{DONE_MARK} already present; nothing to do")
        return 0

    if not DRY:
        if LOCK_DIR.exists():
            pidf = LOCK_DIR / "pid"
            old = pidf.read_text().strip() if pidf.exists() else ""
            rc, _, _ = sh(f"kill -0 {old} 2>/dev/null") if old else (1, "", "")
            if rc == 0:
                log(f"another orchestrator (pid {old}) is live; exiting")
                return 3
            log(f"stale lock (pid {old or '?'} dead); taking over")
            shutil.rmtree(LOCK_DIR)
        LOCK_DIR.mkdir()
        (LOCK_DIR / "pid").write_text(str(os.getpid()))

    try:
        t0 = time.time()
        log("========== FINAL WINDOW ORCHESTRATOR START "
            f"(pid {os.getpid()}, dry_run={DRY}) ==========")
        step0_preconditions()
        step12_requeues()
        step3_review_p46()
        step3b_review_p37()
        step4_review_p95()
        if not DRY:
            SUMMARY["finished_at"] = datetime.now().isoformat()
            SUMMARY["total_elapsed_s"] = round(time.time() - t0, 1)
            atomic_write(SUMMARY_PATH, json.dumps(SUMMARY, ensure_ascii=False,
                                                  indent=2, default=str))
            DONE_MARK.touch()
            log(f"FINAL_WINDOW_DONE written ({DONE_MARK}); "
                f"summary at {SUMMARY_PATH}")
        else:
            log("[dry-run] complete; no ledger edits, no runs, no markers")
        log(f"========== FINAL WINDOW ORCHESTRATOR END "
            f"(total {round(time.time() - t0, 1)}s) ==========")
        return 0
    finally:
        if not DRY and LOCK_DIR.exists():
            shutil.rmtree(LOCK_DIR, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
