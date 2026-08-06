#!/usr/bin/env python3
"""P37 sync_remove__1 NEW-witness control review (EVIDENCE ONLY, no ledger writes).

Context
-------
The 2026-07-30 sign-off requeue of the five L1_P37 probes produced exactly one
FALSIFIED record, ``L1_P37__sync_remove__1`` with a *new* witness at
sparse_extreme / sub_index 2 / seed 50042 ("observed 1 output mismatch",
max_abs_error 0.0175692 vs atol=rtol=1e-2).  The other four probes -- including
``L1_P37__sync_remove__0``, the same operator at a different site -- passed all
100 rounds, sparse_extreme si=2 included.

The signed-off H2 finding voided the *previous* P37 witness round
(boundary_last_element / seed 50040) because the UNMUTATED kernel diverged from
the reference on that very round.  The L1_P37 kernel is a Frobenius-norm
normaliser whose phase 2 reads every block's partial sum out of global memory
with no grid-level barrier, so it is racy before any mutation is applied.  The
new witness therefore needs the same control before it can be called a defect.

Protocol (mirrors _final_window_go.py STEP3b, retuned to this witness round)
---------------------------------------------------------------------------
Round-position derivation, read out of the production code, not guessed:
``scripts/_mutant_worker.py`` computes the stress seed as
``seed = base_seed + equiv_runs + sub_index``; the production driver
``scripts/run_e1_cse_falsify.py`` uses FALSIFY_BASE_SEED=50000 and
FALSIFY_EQUIV_RUNS=40, so sub_index 2 is seed 50000+40+2 = 50042.  Setting
``equiv_runs=0`` and ``base_seed=50040`` reproduces seeds 50040/50041/50042 for
si=0/1/2 with the witness at si=2, exactly as in production.  The derivation is
policy-list independent, and the stress input itself is a pure function of the
template geometry/dtype plus the round seed: L1_P37 ``get_inputs`` returns a
single float32 ``rand(112,64,512,512)``, i.e. an all-float tree, so the worker's
template cache reuses the si=0 template (also generated under seed 50040 in
production, since the first stress round always has seed base+equiv_runs+0) and
``_sparse_extreme`` regenerates every value from ``torch.Generator(50042)``.
``get_init_inputs`` returns ``[]`` and ``ModelNew`` takes no arguments, so the
base_seed change cannot perturb model construction either.

``round_timeout=300`` is the production value for the run that produced this
witness: _signoff_orch.py exports ``MK_CSE_ROUND_TIMEOUT=300`` and
run_e1_cse_falsify.py reads it.  (The 90s in STEP3b was the older final-window
value; using it here would risk turning a numeric question into a timeout.)

Three groups, nine independent worker processes / CUDA contexts:
  1. unmutated original as candidate vs the reference path, x3 -- any
     over-tolerance diff here is mutation-independent (kernel-level);
  2. ``L1_P37__sync_remove__1`` x3 -- does the new witness reproduce;
  3. ``L1_P37__sync_remove__0`` x3 -- same operator, different site, 100/100
     in production; a divergence here would also point at the kernel.

Scheduling
----------
The critical path owns the GPU.  This script pre-builds every worker config,
then polls for ``SIGNOFF_ORCH_DONE`` at 5s and fires immediately, so its
``_mutant_worker.py`` processes are up long before _b9_chain_trigger.py can
collect the two consecutive clean polls (60s apart) it needs to start the B9
wave.  The trigger is NOT modified: it detects ``_mutant_worker.py`` by /proc
cmdline scan and a GPU compute app by nvidia-smi, and this review produces both,
so B9 keeps waiting on its own logic.

Nothing here writes the ledger.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

MK = Path("/root/mk_v2")
RUNS = Path("/root/mk_v2_runs")
E1 = RUNS / "e1"
OUTDIR = E1 / "final_window_review" / "p37_sync_remove_1_newwitness"
SIGNOFF_DONE = E1 / "SIGNOFF_ORCH_DONE"
LOG = OUTDIR / "review.log"
LOCK = OUTDIR / "review.lock"
SUMMARY_FILE = OUTDIR / "review_summary.json"
STATUS_FILE = OUTDIR / "STATUS.json"

WITNESS_PROBE = "L1_P37__sync_remove__1"
LATERAL_PROBE = "L1_P37__sync_remove__0"
CONTROL_ID = "L1_P37__ORIGINAL_CONTROL_sparse_extreme"

WITNESS_POLICY = "sparse_extreme"
WITNESS_SUB_INDEX = 2
WITNESS_SEED = 50042
WITNESS_ORIGINAL_MAX_ABS_ERROR = 0.0175692

REPS = 3
WORKER_TIMEOUT_S = 1800          # whole-probe budget for 3 stress rounds
ROUND_TIMEOUT_S = 300            # production value of the sign-off requeue run

POLL_S = 5
MAX_WAIT_CRITICAL_S = 3600       # after the marker, wait this long for idle
CRITICAL_NEEDLES = ("_mutant_worker.py", "run_e1_cse_falsify.py",
                    "_signoff_orch.py")
B9_NEEDLES = ("_b9_calib_driver_v2.py", "_b9_calib_driver.py", "guard_b9")


def log(msg):
    line = "[nw-review %s] %s" % (datetime.now().strftime("%F %T"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _ppid(pid):
    try:
        for line in open("/proc/%d/status" % pid, encoding="utf-8"):
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def find_processes(needle):
    """/proc cmdline scan minus self and ancestors.  `pgrep -f` is banned in
    this campaign: it matches the ssh command line carrying the pattern."""
    excluded = set()
    pid = os.getpid()
    while pid and pid != 1:
        excluded.add(pid)
        pid = _ppid(pid)
    hits = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid in excluded:
            continue
        try:
            raw = Path("/proc/%d/cmdline" % pid).read_bytes()
        except OSError:
            continue
        cmdline = raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
        if needle in cmdline:
            hits.append((pid, cmdline[:160]))
    return hits


def scan(needles):
    found = []
    for needle in needles:
        for pid, cmdline in find_processes(needle):
            found.append((needle, pid, cmdline))
    return found


# ---------------------------------------------------------------------------
# pre-arm: everything expensive happens before the wait, so firing is instant
# ---------------------------------------------------------------------------

def build_configs():
    sys.path.insert(0, str(MK))
    import scripts.run_e1_probe_study as ps
    import scripts.run_e1_cse_falsify as fal

    stress_base = fal.FALSIFY_BASE_SEED + fal.FALSIFY_EQUIV_RUNS
    assert stress_base + WITNESS_SUB_INDEX == WITNESS_SEED, (
        "seed derivation drifted: %d + %d != %d"
        % (stress_base, WITNESS_SUB_INDEX, WITNESS_SEED))

    common = {
        "equiv_runs": 0,
        "base_seed": stress_base,
        "stress_policies": [WITNESS_POLICY],
        "stress_repeats": WITNESS_SUB_INDEX + 1,
        "round_timeout": ROUND_TIMEOUT_S,
    }

    probe_files = ps._load_probe_files(E1)

    def find(probe_id):
        for kf in probe_files:
            for probe in kf["probes"]:
                if probe["probe_id"] == probe_id:
                    return kf, probe
        raise KeyError(probe_id)

    def base_cfg(kf, probe, mutant_id, code):
        problem_file = ps._resolve_problem_file(
            MK / "KernelBench", kf["kernel"]["level"], kf["kernel"]["problem_id"])
        return dict({
            "mode": "equiv",
            "mutant_id": mutant_id,
            "problem_file": str(problem_file),
            "kernel_code": kf["kernel_source"],
            "mutated_code": code,
            "operator_name": probe["operator_name"],
            "device": ps.BASELINE_PROTOCOL["device"],
            "atol": ps.BASELINE_PROTOCOL["atol"],
            "rtol": ps.BASELINE_PROTOCOL["rtol"],
        }, **common)

    wkf, wprobe = find(WITNESS_PROBE)
    lkf, lprobe = find(LATERAL_PROBE)

    plan = []
    for rep in range(1, REPS + 1):
        plan.append(("control_rep%d" % rep, "control",
                     base_cfg(wkf, wprobe, CONTROL_ID, wkf["kernel_source"])))
    for rep in range(1, REPS + 1):
        plan.append(("witness_rep%d" % rep, "witness",
                     base_cfg(wkf, wprobe, WITNESS_PROBE, wprobe["mutated_code"])))
    for rep in range(1, REPS + 1):
        plan.append(("lateral_rep%d" % rep, "lateral",
                     base_cfg(lkf, lprobe, LATERAL_PROBE, lprobe["mutated_code"])))
    return ps, common, plan


# ---------------------------------------------------------------------------
# evidence extraction
# ---------------------------------------------------------------------------

_ERR_RE = re.compile(r"max_abs_error=([0-9.eE+-]+)")


def max_abs_error(oracle):
    for mismatch in ((oracle or {}).get("mismatches") or []):
        found = _ERR_RE.search(mismatch.get("message", ""))
        if found:
            return float(found.group(1))
    return None


def round_digest(result):
    rounds = []
    for trial in ((result or {}).get("trials") or []):
        rounds.append({
            "sub_index": trial.get("sub_index"),
            "seed": trial.get("seed"),
            "status": trial.get("status"),
            "max_abs_error": max_abs_error(trial.get("oracle")),
            "reason": (trial.get("reason") or "")[:200],
        })
    return rounds


def rep_verdict(result, timed_out):
    """(verdict, diverged_sub_index, max_abs_error) for one worker call."""
    if timed_out or result is None:
        return "worker_failure", None, None
    status = result.get("validation_status")
    divergence = result.get("divergence")
    if divergence:
        return ("diverged", divergence.get("sub_index"),
                max_abs_error(divergence.get("oracle")))
    if status == "pass":
        return "pass", None, None
    if (result.get("round_timeouts") or 0) > 0:
        return "round_timeout", None, None
    return "other", None, None


# ---------------------------------------------------------------------------

def wait_for_go():
    log("pre-armed; waiting for %s (poll %ds)" % (SIGNOFF_DONE, POLL_S))
    announced = False
    while not SIGNOFF_DONE.is_file():
        if not announced:
            procs = scan(CRITICAL_NEEDLES)
            log("critical path: %s" % (
                ", ".join("%s pid=%d" % (n, p) for n, p, _ in procs)
                or "no process"))
            announced = True
        time.sleep(POLL_S)
    log("%s present -> go" % SIGNOFF_DONE.name)

    # The payload's `bash -c ... &` subshell carries the same command line and
    # exits together with the payload, so it is a correct liveness proxy and is
    # deliberately not filtered out here.
    deadline = time.time() + MAX_WAIT_CRITICAL_S
    last = None
    while time.time() < deadline:
        procs = scan(CRITICAL_NEEDLES)
        if not procs:
            break
        current = sorted(p for _, p, _ in procs)
        if current != last:
            log("critical-path process still alive, holding: %s"
                % ", ".join("%s pid=%d" % (n, p) for n, p, _ in procs))
            last = current
        time.sleep(POLL_S)
    else:
        log("WARNING: critical-path processes still alive after %ds; "
            "starting anyway would risk contention -> abort"
            % MAX_WAIT_CRITICAL_S)
        return False

    b9 = scan(B9_NEEDLES)
    if b9:
        log("ABORT: the B9 wave won the race (%s).  Not starting: a concurrent "
            "run is exactly the configuration that OOM-killed a worker before. "
            "Leaving the decision to a human; the B9 trigger is untouched."
            % ", ".join("%s pid=%d" % (n, p) for n, p, _ in b9))
        STATUS_FILE.write_text(json.dumps({
            "state": "deferred_b9_started_first",
            "b9_processes": [{"needle": n, "pid": p, "cmdline": c}
                             for n, p, c in b9],
            "at": datetime.now().isoformat(),
        }, indent=2), encoding="utf-8")
        return False
    log("box idle (no critical path, no B9) -> starting the review")
    return True


def check():
    """Read-only pre-flight: resolve probes, prove the seed derivation, and
    show what the trigger's /proc scan would see.  Launches nothing."""
    OUTDIR.mkdir(parents=True, exist_ok=True)
    ps, common, plan = build_configs()
    print("protocol:", json.dumps(common))
    for name, group, cfg in plan:
        print("  %-14s %-8s mutant_id=%s mutated_len=%d problem_file=%s"
              % (name, group, cfg["mutant_id"], len(cfg["mutated_code"]),
                 cfg["problem_file"]))
    wcfg = [c for n, g, c in plan if g == "witness"][0]
    ccfg = [c for n, g, c in plan if g == "control"][0]
    print("control mutated_code == kernel_code:",
          ccfg["mutated_code"] == ccfg["kernel_code"])
    print("witness mutated_code == kernel_code:",
          wcfg["mutated_code"] == wcfg["kernel_code"])
    print("stress seeds:", [common["base_seed"] + common["equiv_runs"] + si
                            for si in range(common["stress_repeats"])])
    print("worker path:", ps.WORKER_CORRECTED)
    print("critical path now:", scan(CRITICAL_NEEDLES))
    print("b9 now:", scan(B9_NEEDLES))
    print("SIGNOFF_ORCH_DONE:", SIGNOFF_DONE.is_file())
    return 0


def main():
    if "--check" in sys.argv:
        return check()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK, "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("another review holds the lock -> exit (idempotent)")
        return 0
    handle.seek(0)
    handle.truncate()
    handle.write("%d\n" % os.getpid())
    handle.flush()

    if SUMMARY_FILE.exists():
        log("review_summary.json already present -> nothing to do (idempotent)")
        return 0

    os.environ["PATH"] = ("/usr/local/cuda/bin:/root/miniconda3/bin:"
                          "/usr/local/bin:/usr/bin:/bin")
    os.environ["TORCH_EXTENSIONS_DIR"] = str(RUNS / "torch_ext")
    os.environ["MK_GPU_MEMORY_FRACTION"] = "0.92"

    log("=== new-witness review start pid=%d ===" % os.getpid())
    ps, common, plan = build_configs()
    log("protocol: %s" % json.dumps(common))
    log("witness round: policy=%s sub_index=%d seed=%d (base_seed+equiv_runs+si "
        "= 50000+40+2), original max_abs_error=%s"
        % (WITNESS_POLICY, WITNESS_SUB_INDEX, WITNESS_SEED,
           WITNESS_ORIGINAL_MAX_ABS_ERROR))
    log("plan: %s" % ", ".join(name for name, _, _ in plan))
    STATUS_FILE.write_text(json.dumps({
        "state": "armed_waiting_for_signoff_done",
        "at": datetime.now().isoformat(),
    }, indent=2), encoding="utf-8")

    if not wait_for_go():
        return 2

    STATUS_FILE.write_text(json.dumps({
        "state": "running", "started_at": datetime.now().isoformat(),
    }, indent=2), encoding="utf-8")

    scratch = OUTDIR / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    groups = {"control": [], "witness": [], "lateral": []}
    t_all = time.time()
    for name, group, cfg in plan:
        t0 = time.time()
        result, timed_out, wall_ms, stdout, stderr = ps.run_worker(
            cfg, WORKER_TIMEOUT_S, scratch)
        verdict, sub_index, err = rep_verdict(result, timed_out)
        rounds = round_digest(result)
        record = {
            "name": name,
            "group": group,
            "cfg_digest": {k: cfg[k] for k in
                           ("mutant_id", "equiv_runs", "base_seed",
                            "stress_policies", "stress_repeats",
                            "round_timeout", "atol", "rtol")},
            "verdict": verdict,
            "diverged_sub_index": sub_index,
            "max_abs_error": err,
            "wall_ms": round(wall_ms, 1),
            "timed_out": timed_out,
            "validation_status": (result or {}).get("validation_status"),
            "valid_rounds": (result or {}).get("valid_rounds"),
            "round_timeouts": (result or {}).get("round_timeouts"),
            "rounds": rounds,
            "result": result,
        }
        (OUTDIR / ("%s_result.json" % name)).write_text(
            json.dumps(record, indent=2, default=str), encoding="utf-8")
        if stderr.strip() or result is None:
            (OUTDIR / ("%s_worker.log" % name)).write_text(
                "STDOUT:\n%s\n\nSTDERR:\n%s\n" % (stdout, stderr),
                encoding="utf-8")
        groups[group].append({k: v for k, v in record.items() if k != "result"})
        log("%s: verdict=%s sub_index=%s max_abs_error=%s wall=%.1fs "
            "rounds=%s" % (name, verdict, sub_index, err,
                           (time.time() - t0),
                           [(r["sub_index"], r["status"], r["max_abs_error"])
                            for r in rounds]))

    def all_rounds(group):
        return [r for rep in groups[group] for r in rep["rounds"]]

    control_diverged = [r for r in all_rounds("control") if r["status"] == "fail"]
    control_clean = (all(rep["verdict"] == "pass" for rep in groups["control"])
                     and not control_diverged)
    witness_repro = [rep for rep in groups["witness"]
                     if rep["verdict"] == "diverged"
                     and rep["diverged_sub_index"] == WITNESS_SUB_INDEX]
    witness_stable = len(witness_repro) == REPS
    lateral_clean = all(rep["verdict"] == "pass" for rep in groups["lateral"])

    if control_diverged:
        code = "H2_KERNEL_NUMERIC_SENSITIVITY_SPARSE_EXTREME"
        rec = (
            "支持 H2(内核级数值敏感的又一次显形):未变异 P37 原内核在 "
            "sparse_extreme/seed 50040-50042 同轮位上,candidate 编译路径 vs 参考路径"
            "自身即超差(发散轮 %s)。该轮位对 L1_P37 无判别力,建议作废 "
            "%s 的新 witness,把 sparse_extreme 与 boundary_last_element 一并写入 "
            "L1_P37 的 policy-skip,并对该探针摘账重跑。不改主账。"
            % ([(r["sub_index"], r["seed"], r["max_abs_error"])
                for r in control_diverged], WITNESS_PROBE))
    elif control_clean and witness_stable and lateral_clean:
        code = "H1_TRUE_DEFECT_SITE_SPECIFIC"
        rec = (
            "支持 H1(真缺陷,位点特异):未变异对照 3/3 在同轮位容差内通过,"
            "同算子不同位点的 %s 3/3 也通过,而 %s 在 sub_index=2/seed 50042 上 "
            "3/3 稳定复现超差(误差 %s,原 witness %s)。建议维持 FALSIFIED,"
            "witness 升级为可复现记录。人工确认后入账。"
            % (LATERAL_PROBE, WITNESS_PROBE,
               [rep["max_abs_error"] for rep in groups["witness"]],
               WITNESS_ORIGINAL_MAX_ABS_ERROR))
    elif control_clean and not witness_repro:
        code = "WITNESS_TRANSIENT_HUMAN_REVIEW"
        rec = (
            "对照通过但 witness 未复现(candidate 判定=%s):新 witness 疑为瞬态,"
            "请人工定夺是维持 FALSIFIED、改判还是加大复现次数。不改主账。"
            % [rep["verdict"] for rep in groups["witness"]])
    else:
        code = "MIXED_HUMAN_REVIEW"
        rec = (
            "结果混合(control=%s, witness=%s@si=%s, lateral=%s),"
            "不满足任一清晰判据,请人工逐份复核证据文件。不改主账。"
            % ([rep["verdict"] for rep in groups["control"]],
               [rep["verdict"] for rep in groups["witness"]],
               [rep["diverged_sub_index"] for rep in groups["witness"]],
               [rep["verdict"] for rep in groups["lateral"]]))

    summary = {
        "review": "L1_P37__sync_remove__1 new witness (sign-off requeue)",
        "witness": {
            "probe_id": WITNESS_PROBE,
            "policy": WITNESS_POLICY,
            "sub_index": WITNESS_SUB_INDEX,
            "seed": WITNESS_SEED,
            "original_max_abs_error": WITNESS_ORIGINAL_MAX_ABS_ERROR,
            "original_reason": "observed 1 output mismatch(es); "
                               "170 value(s) exceed rtol=0.01, atol=0.01",
            "source_record": "cse_observations_lane3_signoff_requeue.jsonl",
        },
        "seed_derivation": {
            "formula": "seed = base_seed + equiv_runs + sub_index "
                       "(scripts/_mutant_worker.py, stress round loop)",
            "production": "FALSIFY_BASE_SEED=50000 + FALSIFY_EQUIV_RUNS=40 "
                          "+ sub_index=2 = 50042",
            "review": "base_seed=50040 + equiv_runs=0 + sub_index=2 = 50042",
            "bit_exactness": "L1_P37 get_inputs() is a single float32 "
                             "rand(112,64,512,512) (all-float tree), so the "
                             "worker caches the si=0 template (seed 50040 in "
                             "both production and this review, because the "
                             "first stress round is always base+equiv_runs+0) "
                             "and _sparse_extreme regenerates every value from "
                             "torch.Generator(seed); get_init_inputs() == [] "
                             "and ModelNew() takes no arguments, so the "
                             "base_seed change cannot perturb construction.",
            "round_timeout": "300s = MK_CSE_ROUND_TIMEOUT exported by "
                             "_signoff_orch.py for the run that produced this "
                             "witness",
        },
        "protocol": dict(common, worker_timeout_s=WORKER_TIMEOUT_S, reps=REPS),
        "groups": groups,
        "control_clean": control_clean,
        "control_diverged_rounds": control_diverged,
        "witness_reproductions_at_witness_round": len(witness_repro),
        "lateral_clean": lateral_clean,
        "recommendation_code": code,
        "recommendation": rec,
        "ledger_written": False,
        "elapsed_s": round(time.time() - t_all, 1),
        "finished_at": datetime.now().isoformat(),
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    (OUTDIR / "RECOMMENDATION.txt").write_text(rec + "\n", encoding="utf-8")
    STATUS_FILE.write_text(json.dumps({
        "state": "done", "recommendation_code": code,
        "at": datetime.now().isoformat()}, indent=2), encoding="utf-8")
    log("=== done -> %s (%.1fs) ===" % (code, time.time() - t_all))
    log("主账未改;定级决定留给人工确认")
    return 0


if __name__ == "__main__":
    sys.exit(main())
