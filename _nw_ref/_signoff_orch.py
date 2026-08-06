"""Sign-off rerun orchestrator: drive the 6 signed-off probes to a real grade.

The first attempt was corrupted by resource contention: the B9 calibration ran
four concurrent units (one peaked near 79GB RSS) against the 120GiB cgroup cap
and OOM-killed the CSE worker, so #7 was recorded INCONCLUSIVE at 32/103 rounds
instead of being graded.  B9 is now stopped, so this orchestrator waits for the
in-flight driver, then requeues any probe whose outcome is INCONCLUSIVE and
reruns it under exclusive conditions, up to MAX_ROUNDS times.  Every requeue
archives the superseded record first; nothing is deleted.

Exclusivity is enforced before each launch: if any non-CSE GPU consumer appeared
the round is refused rather than risking another contaminated record.
"""
import json
import os
import subprocess
import time
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
MK = Path("/root/mk_v2")
RUNS = Path("/root/mk_v2_runs")
PY = "/root/miniconda3/bin/python"
ARCHIVE = E1 / "cse_observations_signoff_oom_archive.jsonl"
LOG = RUNS / "signoff_orch.log"
SUMMARY = E1 / "signoff_orch_summary.json"
DONE = E1 / "SIGNOFF_ORCH_DONE"

EXPECT = [
    "L1_P46__index_replace__5",
    "L1_P37__arith_replace__14",
    "L1_P37__sync_remove__1",
    "L1_P37__sync_remove__0",
    "L1_P37__launch_config_mutate__0",
    "L1_P37__epsilon_modify__0",
]
MAX_ROUNDS = 3
BUDGET_S = 5400          # whole-probe budget; the OOM death was at 999s
ROUND_TIMEOUT_S = 300    # per-round watchdog (signed-off #7 review value)
STATE = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "rounds": []}


def log(msg):
    line = f"[{time.strftime('%F %T')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def sh(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def oom_count():
    for p in ("/sys/fs/cgroup/memory.events",
              "/sys/fs/cgroup/memory/memory.oom_control"):
        try:
            for line in open(p, encoding="utf-8"):
                if line.startswith("oom_kill "):
                    return int(line.split()[1])
        except OSError:
            continue
    return None


def cse_driver_pids():
    # bracketed class so the pgrep shell's own command line cannot self-match
    rc, out, _ = sh("pgrep -f 'run_e1_cse_[f]alsify.py' || true")
    mine = {os.getpid(), os.getppid()}
    return [int(x) for x in out.split() if int(x) not in mine] if out else []


def foreign_gpu_procs():
    """GPU consumers that are not our CSE worker/driver."""
    rc, out, _ = sh("nvidia-smi --query-compute-apps=pid --format=csv,noheader")
    foreign = []
    for tok in out.split():
        pid = tok.strip().strip(",")
        if not pid.isdigit():
            continue
        rc2, cmd, _ = sh(f"ps -o cmd= -p {pid} 2>/dev/null || true")
        if not cmd:
            continue
        if "_mutant_worker.py" in cmd or "run_e1_cse_falsify" in cmd:
            continue
        if "nvidia-smi" in cmd or "pgrep" in cmd or "ps -o" in cmd:
            continue
        foreign.append((pid, cmd[:110]))
    return foreign


def atomic_write(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".orch_tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def read_outcomes(tag):
    """probe_id -> record, from one tagged observation file."""
    p = E1 / f"cse_observations_lane3_{tag}.jsonl"
    recs = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                recs[r["probe_id"]] = r
    return recs


def all_outcomes():
    """probe_id -> record across every ledger file that may hold our probes."""
    recs = {}
    for p in sorted(E1.glob("cse_observations_lane*.jsonl")):
        if ".bak" in p.name:
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("probe_id") in EXPECT:
                recs[r["probe_id"]] = (p.name, r)
    return recs


def requeue(probe_ids, reason):
    """Archive the superseded records and clear the ids from every checkpoint."""
    moved = 0
    for p in sorted(E1.glob("cse_observations_lane*.jsonl")):
        if ".bak" in p.name:
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        keep, move = [], []
        for line in lines:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("probe_id") in probe_ids and r.get("outcome") == "INCONCLUSIVE":
                move.append(r)
            else:
                keep.append(line)
        if move:
            with open(ARCHIVE, "a", encoding="utf-8") as fh:
                for r in move:
                    r["orch_requeue"] = {
                        "reason": reason,
                        "archived_at": time.strftime("%FT%T"),
                        "from_file": p.name,
                    }
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            atomic_write(p, "\n".join(keep) + ("\n" if keep else ""))
            moved += len(move)
            log(f"  archived {len(move)} record(s) from {p.name} "
                f"({len(lines)} -> {len(keep)} lines)")
    for p in sorted(E1.glob("cse_completed_lane*.json")):
        if ".bak" in p.name:
            continue
        ids = json.loads(p.read_text(encoding="utf-8"))
        remaining = [i for i in ids if i not in probe_ids]
        if len(remaining) != len(ids):
            atomic_write(p, json.dumps(sorted(remaining)))
            log(f"  {p.name}: {len(ids)} -> {len(remaining)} ids")
    return moved


def launch(tag):
    env = os.environ.copy()
    env["PATH"] = "/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin"
    env["TORCH_EXTENSIONS_DIR"] = str(RUNS / "torch_ext")
    env["MK_GPU_MEMORY_FRACTION"] = "0.92"
    env["MK_CSE_ROUND_TIMEOUT"] = str(ROUND_TIMEOUT_S)
    cmd = [PY, "-u", "scripts/run_e1_cse_falsify.py",
           "--out-dir", str(E1), "--kernelbench-root", "KernelBench",
           "--timeout", str(BUDGET_S),
           "--lane-plan", str(E1 / "cse_lane_plan.json"),
           "--lane", "3", "--lane-tag", tag]
    dlog = RUNS / f"e1_cse_lane3_{tag}.log"
    log(f"  launching tag={tag} budget={BUDGET_S}s round_watchdog={ROUND_TIMEOUT_S}s")
    t0 = time.time()
    with open(dlog, "ab") as fh:
        rc = subprocess.call(cmd, cwd=str(MK), env=env, stdout=fh, stderr=fh)
    return rc, round(time.time() - t0, 1)


def wait_for_inflight():
    pids = cse_driver_pids()
    if not pids:
        log("no in-flight CSE driver")
        return
    log(f"waiting for in-flight CSE driver {pids} (poll 60s)")
    while cse_driver_pids():
        time.sleep(60)
    log("in-flight driver exited")


def main():
    log("=== sign-off orchestrator start ===")
    oom0 = oom_count()
    log(f"oom_kill baseline: {oom0}")
    wait_for_inflight()

    for rnd in range(1, MAX_ROUNDS + 1):
        found = all_outcomes()
        missing = [i for i in EXPECT if i not in found]
        bad = sorted(i for i, (_, r) in found.items()
                     if r.get("outcome") == "INCONCLUSIVE")
        good = {i: r.get("outcome") for i, (_, r) in found.items()
                if r.get("outcome") != "INCONCLUSIVE"}
        log(f"round {rnd}: graded={len(good)} inconclusive={bad} missing={missing}")
        log(f"  graded detail: {good}")
        todo = sorted(set(bad) | set(missing))
        if not todo:
            log("all six probes graded; no requeue needed")
            break

        foreign = foreign_gpu_procs()
        if foreign:
            log(f"REFUSING round {rnd}: foreign GPU consumer(s) present {foreign} "
                "-- a contended rerun would only produce another tainted record")
            STATE["rounds"].append({"round": rnd, "refused": True,
                                    "foreign": foreign})
            break

        oom_before = oom_count()
        if bad:
            log(f"requeueing {bad}")
            requeue(set(bad), "resource-contention OOM (B9 concurrency); "
                              "grade invalid, exclusive rerun required")
        tag = f"signoff_rerun{rnd + 1}"
        rc, elapsed = launch(tag)
        oom_after = oom_count()
        recs = read_outcomes(tag)
        outcomes = {i: r.get("outcome") for i, r in recs.items()}
        detail = {i: {"outcome": r.get("outcome"),
                      "valid_rounds": r.get("valid_rounds"),
                      "wall_ms": r.get("wall_ms"),
                      "timed_out": r.get("timed_out")}
                  for i, r in recs.items()}
        log(f"round {rnd} done: rc={rc} elapsed={elapsed}s "
            f"oom_kill {oom_before}->{oom_after}")
        log(f"  outcomes: {json.dumps(detail, ensure_ascii=False)}")
        STATE["rounds"].append({
            "round": rnd, "tag": tag, "exit": rc, "elapsed_s": elapsed,
            "requeued": bad, "missing_before": missing,
            "oom_kill": [oom_before, oom_after], "detail": detail})
        atomic_write(SUMMARY, json.dumps(STATE, indent=2, ensure_ascii=False))

    found = all_outcomes()
    final = {i: (f, r.get("outcome"), r.get("valid_rounds"))
             for i, (f, r) in found.items()}
    STATE["final"] = {i: {"file": f, "outcome": o, "valid_rounds": v}
                      for i, (f, o, v) in final.items()}
    STATE["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    STATE["oom_kill_total"] = oom_count()
    atomic_write(SUMMARY, json.dumps(STATE, indent=2, ensure_ascii=False))
    DONE.write_text("", encoding="utf-8")
    log("=== final state ===")
    for i in EXPECT:
        log(f"  {i}: {final.get(i, 'MISSING')}")
    log("SIGNOFF_ORCH_DONE")


if __name__ == "__main__":
    main()
