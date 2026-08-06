#!/usr/bin/env python3
"""WC-1: witness confirmation protocol + kernel determinism audit (E1).

Pre-registered protocol (see docstring of ``PROTOCOL`` below).  Two criteria,
both evaluated with the *production* worker at the *production* round position:

  (a) CONTROL / kernel determinism.  The unmutated original kernel is replayed
      as the candidate against the reference path at the witness round position
      n_A times.  All n_A replays must agree within the production tolerance.
      A single divergence proves the (kernel, round position) pair carries
      mutation-independent nondeterminism, so no witness observed there can be
      attributed to the mutation.

  (b) CANDIDATE / witness reproduction.  The mutant is replayed at the same
      round position n_B times; at least k=1 must reproduce a divergence.

Both criteria map onto a single worker invocation each, because
``_equiv_mode`` returns at the first diverging round: "all n_A pass" is
"the control invocation ran to completion", and "at least 1 of n_B
reproduces" is "the candidate invocation aborted with a divergence".

Round-position fidelity.  ``scripts/_mutant_worker.py`` computes the stress
seed as ``base_seed + equiv_runs + sub_index`` and re-seeds every RNG at the
top of every round, and model construction is seeded from ``base_seed``.  The
audit therefore keeps ``base_seed`` and ``equiv_runs`` at their *production*
values (equiv: 10000/20, CSE falsification: 50000/40) so that constructor RNG,
input template and per-round input are bit-identical to production, and obtains
the n replays by repeating the policy name inside ``stress_policies`` (the
worker loops ``for policy_name in stress_policies: for si in range(...)``, so a
repeated name replays the same (policy, sub_index, seed) triple).

Nothing here writes the E1 ledger.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

MK = Path("/root/mk_v2")
RUNS = Path("/root/mk_v2_runs")
E1 = RUNS / "e1"
OUTDIR = E1 / "witness_confirmation"
INVENTORY = E1 / "_wc_witness_inventory.json"
COSTS = E1 / "_wc_round_wall.json"   # measured s/round incl. input generation
STARTUP_S = 70.0

PROTOCOL = {
    "id": "WC-1",
    "n_A": 50,          # control replays per (kernel, round position)
    "n_B": 20,          # candidate replays per witness
    "k": 1,             # reproductions required out of n_B
    "round_timeout_s": 300,
    # Production protocol constants, read out of the drivers:
    # run_e1_probe_study.EQUIV_BASE_SEED/EQUIV_RUNS and the default
    # stress_repeats=2 (verified against the observation histograms:
    # equiv sub_index in {0,1}); run_e1_cse_falsify.FALSIFY_BASE_SEED /
    # FALSIFY_EQUIV_RUNS / FALSIFY_STRESS_REPEATS=3 (histogram {0,1,2}).
    "equiv": {"base_seed": 10000, "equiv_runs": 20, "stress_repeats": 2},
    "cse": {"base_seed": 50000, "equiv_runs": 40, "stress_repeats": 3},
}

WORKER_TIMEOUT_FLOOR_S = 900
WORKER_TIMEOUT_CAP_S = 5400

# Only the lane drivers actually compete for the GPU/RAM.  The guard, the chain
# trigger and the stage-1 chainer stay resident by design while
# PAUSED_FOR_SIGNOFF_RERUN is in place, and must not be treated as a conflict.
B9_NEEDLES = ("_b9_calib_driver_v2.py", "_b9_calib_driver.py")
B9_PAUSE_MARKER = RUNS / "e3_b9_calib" / "PAUSED_FOR_SIGNOFF_RERUN"


def log(msg, logfile):
    line = "[wc-audit %s] %s" % (datetime.now().strftime("%F %T"), msg)
    print(line, flush=True)
    with open(logfile, "a", encoding="utf-8") as fh:
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
    """/proc cmdline scan minus self and ancestors (``pgrep -f`` is banned)."""
    excluded, pid = set(), os.getpid()
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


def b9_alive():
    found = []
    for needle in B9_NEEDLES:
        for pid, cmdline in find_processes(needle):
            found.append((needle, pid, cmdline))
    return found


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def load_inventory():
    return json.load(open(INVENTORY, encoding="utf-8"))


def position_of(rec):
    d = rec.get("divergence") or {}
    return {
        "round_type": d.get("round_type"),
        "policy": d.get("policy"),
        "sub_index": d.get("sub_index"),
        "round_index": d.get("round_index"),
        "seed": d.get("seed"),
    }


def load_shortcut():
    """Which kernels may skip the production random-round prefix.

    The worker builds both models under ``_seed_all(base_seed)``, so moving
    base_seed to the witness stress seed (with equiv_runs = 0) is bit-exact only
    when construction does not consume the RNG.  ``_wc28_probe.py`` checks that
    directly -- it builds each kernel under 10000/10020/50000/50040 and compares
    every parameter and buffer -- and this file records the answer.  Kernels that
    fail the check replay the full production prefix.
    """
    path = E1 / "_wc_seed_shortcut.json"
    if not path.exists():
        return {}
    data = json.load(open(path, encoding="utf-8"))
    return {k: bool(v.get("construction_seed_independent")) for k, v in data.items()}


def build_plan(inv, n_a=None, n_b=None):
    n_a = n_a or PROTOCOL["n_A"]
    n_b = n_b or PROTOCOL["n_B"]
    shortcut = load_shortcut()
    by_kernel_stage = defaultdict(list)
    skipped = []
    for rec in inv:
        pos = position_of(rec)
        if pos["round_type"] is None:
            skipped.append({"probe_id": rec["probe_id"], "kernel": rec["kernel"],
                            "stage": rec["stage"],
                            "why": "no numeric divergence round "
                                   "(non-numeric witness, e.g. SPEC_VIOLATION)"})
            continue
        by_kernel_stage[(rec["kernel"], rec["stage"])].append((rec, pos))

    control_cells, confirm_cells = [], []
    for (kernel, stage), rows in sorted(by_kernel_stage.items()):
        proto = PROTOCOL["cse" if stage == "cse" else "equiv"]
        stress = [(r, p) for r, p in rows if p["round_type"] == "stress"]
        random_rounds = [(r, p) for r, p in rows if p["round_type"] == "random"]

        # The control unit is (kernel, stage, stress policy): kernel-level
        # nondeterminism is a property of the *input distribution* a policy
        # induces, not of one seed inside it (L1_P37 diverges at
        # sparse_extreme/50040 and its witness sits at sparse_extreme/50042).
        # Each of the n_A replays therefore covers the whole production
        # sub_index range for that policy, so a unit accumulates
        # n_A x stress_repeats control rounds.
        reps = proto["stress_repeats"]
        by_policy = defaultdict(set)
        for _, p in stress:
            by_policy[p["policy"]].add(p["sub_index"] or 0)
        for policy, subs in sorted(by_policy.items()):
            if shortcut.get(kernel):
                cfg = {
                    "base_seed": proto["base_seed"] + proto["equiv_runs"],
                    "equiv_runs": 0,
                    "stress_policies": [policy] * n_a,
                    "stress_repeats": reps,
                }
                rounds = n_a * reps
            else:
                cfg = {
                    "base_seed": proto["base_seed"],
                    "equiv_runs": proto["equiv_runs"],
                    "stress_policies": [policy] * n_a,
                    "stress_repeats": reps,
                }
                rounds = proto["equiv_runs"] + n_a * reps
            control_cells.append({
                "cell_id": "ctrl__%s__%s__%s" % (kernel, stage, policy),
                "kind": "control", "kernel": kernel, "stage": stage,
                "positions": [(policy, si) for si in range(reps)],
                "witness_sub_indices": sorted(subs),
                "probe_ids": sorted({r["probe_id"] for r, p in stress
                                     if p["policy"] == policy}),
                "seed_shortcut": bool(shortcut.get(kernel)),
                "cfg": cfg, "replays": n_a, "rounds": rounds,
            })
        # Criterion (a) is a property of (kernel, round position), not of the
        # probe, so witnesses sharing a random round position share one set of
        # control replays.
        random_by_index = defaultdict(list)
        for rec, pos in random_rounds:
            random_by_index[pos["round_index"] or 0].append(rec)
        # Random positions cannot be replayed at an identical seed: the worker
        # assigns seed = base_seed + i over distinct i.  The n_A replays are
        # therefore n_A independent draws from the *same* input generator that
        # produced the witness round, the witness round included (round i is
        # reached whenever equiv_runs > i).  This keeps n_A uniform across
        # position types at one invocation instead of n_A.
        for ridx, recs in sorted(random_by_index.items()):
            runs = max(n_a, ridx + 1)
            control_cells.append({
                "cell_id": "ctrl__%s__%s__rand%d" % (kernel, stage, ridx),
                "kind": "control", "kernel": kernel, "stage": stage,
                "positions": [("__random__", ridx)],
                "probe_ids": sorted(r["probe_id"] for r in recs),
                "cfg": {
                    "base_seed": proto["base_seed"],
                    "equiv_runs": runs,
                    "stress_policies": [],
                    "stress_repeats": 0,
                },
                "replays": runs,
                "rounds": runs,
            })

        for rec, pos in rows:
            if pos["round_type"] == "stress":
                si = pos["sub_index"] or 0
                if shortcut.get(kernel):
                    cfg = {
                        "base_seed": proto["base_seed"] + proto["equiv_runs"] + si,
                        "equiv_runs": 0,
                        "stress_policies": [pos["policy"]] * n_b,
                        "stress_repeats": 1,
                    }
                    rounds = n_b
                else:
                    cfg = {
                        "base_seed": proto["base_seed"],
                        "equiv_runs": proto["equiv_runs"],
                        "stress_policies": [pos["policy"]] * n_b,
                        "stress_repeats": si + 1,
                    }
                    rounds = proto["equiv_runs"] + n_b * (si + 1)
            else:
                # A random witness round is reproduced by replaying the
                # production prefix up to and including that round exactly once
                # (the seed is unique to the round, so k-of-n does not apply;
                # this cell answers "does the mutant still diverge there").
                cfg = {
                    "base_seed": proto["base_seed"],
                    "equiv_runs": (pos["round_index"] or 0) + 1,
                    "stress_policies": [],
                    "stress_repeats": 0,
                }
                rounds = (pos["round_index"] or 0) + 1
            confirm_cells.append({
                "cell_id": "conf__%s__%s" % (rec["probe_id"], stage),
                "kind": "confirm", "kernel": kernel, "stage": stage,
                "probe_id": rec["probe_id"], "position": pos,
                "cfg": cfg, "replays": n_b if pos["round_type"] == "stress" else 1,
                "rounds": rounds,
            })
    return control_cells, confirm_cells, skipped


def round_cost_s(costs, kernel):
    v = costs.get(kernel)
    if isinstance(v, list):
        v = v[1] or v[0]
        return (v or 500.0) / 1000.0
    return float(v if v is not None else 0.5)


def estimate(cells, costs):
    return sum(STARTUP_S + c["rounds"] * round_cost_s(costs, c["kernel"])
               for c in cells)


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------

_ERR_RE = re.compile(r"max_abs_error=([0-9.eE+-]+)")


def max_abs_error(oracle):
    for mismatch in ((oracle or {}).get("mismatches") or []):
        found = _ERR_RE.search(mismatch.get("message", ""))
        if found:
            return float(found.group(1))
    return None


def round_digest(result):
    out = []
    for trial in ((result or {}).get("trials") or []):
        out.append({
            "round_type": trial.get("round_type"),
            "policy": trial.get("policy"),
            "sub_index": trial.get("sub_index"),
            "round_index": trial.get("round_index"),
            "seed": trial.get("seed"),
            "status": trial.get("status"),
            "max_abs_error": max_abs_error(trial.get("oracle")),
            "reason": (trial.get("reason") or "")[:200],
        })
    return out


def build_cfg_resolver():
    sys.path.insert(0, str(MK))
    import scripts.run_e1_probe_study as ps

    probe_files = ps._load_probe_files(E1)
    kf_by_kernel, probe_index = {}, {}
    for kf in probe_files:
        kk = kf["kernel"]
        kid = "L%s_P%s" % (kk["level"], kk["problem_id"])
        kf_by_kernel[kid] = kf
        for probe in kf["probes"]:
            probe_index[probe["probe_id"]] = (kf, probe)

    def problem_file(kf):
        return str(ps._resolve_problem_file(
            MK / "KernelBench", kf["kernel"]["level"], kf["kernel"]["problem_id"]))

    def make(cell):
        if cell["kind"] == "control":
            kf = kf_by_kernel[cell["kernel"]]
            mutant_id = "%s__WC_AUDIT_CONTROL__%s" % (cell["kernel"], cell["stage"])
            mutated = kf["kernel_source"]
            operator_name = ""
        else:
            kf, probe = probe_index[cell["probe_id"]]
            mutant_id = cell["probe_id"]
            mutated = probe["mutated_code"]
            operator_name = probe["operator_name"]
        cfg = {
            "mode": "equiv",
            "mutant_id": mutant_id,
            "problem_file": problem_file(kf),
            "kernel_code": kf["kernel_source"],
            "mutated_code": mutated,
            "operator_name": operator_name,
            "device": ps.BASELINE_PROTOCOL["device"],
            "atol": ps.BASELINE_PROTOCOL["atol"],
            "rtol": ps.BASELINE_PROTOCOL["rtol"],
            "round_timeout": PROTOCOL["round_timeout_s"],
        }
        cfg.update(cell["cfg"])
        return cfg

    return ps, make


def order_cells(cells, costs):
    """CSE first (it carries the headline 9-of-453 figure), cheap first inside
    each stage so that most cells land early."""
    return sorted(cells, key=lambda c: (c["stage"] != "cse",
                                        STARTUP_S + c["rounds"]
                                        * round_cost_s(costs, c["kernel"])))


def shard(cells, lane, lanes):
    return [c for i, c in enumerate(cells) if lanes <= 1 or i % lanes == lane]


def run_cells(cells, tag, costs, logfile, force=False):
    ps, make = build_cfg_resolver()
    resdir = OUTDIR / "cells"
    resdir.mkdir(parents=True, exist_ok=True)
    scratch = OUTDIR / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)

    done = 0
    for idx, cell in enumerate(cells, 1):
        path = resdir / ("%s.json" % cell["cell_id"])
        if path.exists() and not force:
            done += 1
            continue
        cfg = make(cell)
        budget = int(min(WORKER_TIMEOUT_CAP_S,
                         max(WORKER_TIMEOUT_FLOOR_S,
                             2.5 * cell["rounds"] * round_cost_s(costs, cell["kernel"])
                             + 2 * STARTUP_S)))
        t0 = time.time()
        result, timed_out, wall_ms, stdout, stderr = ps.run_worker(cfg, budget, scratch)
        rounds = round_digest(result)
        divergence = (result or {}).get("divergence")
        record = {
            "cell_id": cell["cell_id"],
            "kind": cell["kind"],
            "kernel": cell["kernel"],
            "stage": cell["stage"],
            "probe_id": cell.get("probe_id"),
            "probe_ids": cell.get("probe_ids"),
            "positions": cell.get("positions"),
            "position": cell.get("position"),
            "planned_replays": cell["replays"],
            "planned_rounds": cell["rounds"],
            "cfg_digest": {k: cfg[k] for k in
                           ("mutant_id", "base_seed", "equiv_runs",
                            "stress_repeats", "round_timeout", "atol", "rtol")},
            "stress_policy_multiset": cell["cfg"]["stress_policies"][:6],
            "validation_status": (result or {}).get("validation_status"),
            "valid_rounds": (result or {}).get("valid_rounds"),
            "round_timeouts": (result or {}).get("round_timeouts"),
            "timed_out": timed_out,
            "worker_budget_s": budget,
            "wall_s": round(wall_ms / 1000.0, 1),
            "divergence": divergence,
            "rounds": rounds,
            "errors": (result or {}).get("errors"),
            "finished_at": datetime.now().isoformat(),
        }
        if result is None or stderr.strip():
            (resdir / ("%s.workerlog" % cell["cell_id"])).write_text(
                "STDOUT:\n%s\n\nSTDERR:\n%s\n" % (stdout, stderr), encoding="utf-8")
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1,
                                   default=str), encoding="utf-8")
        done += 1
        nfail = sum(1 for r in rounds if r["status"] == "fail")
        log("[%s %d/%d] %s status=%s rounds=%d fail=%d wall=%.1fs budget=%ds"
            % (tag, idx, len(cells), cell["cell_id"],
               record["validation_status"], len(rounds), nfail,
               time.time() - t0, budget), logfile)
    return done


# ---------------------------------------------------------------------------

def cmd_plan(args):
    inv = load_inventory()
    costs = json.load(open(COSTS)) if COSTS.exists() else {}
    control, confirm, skipped = build_plan(inv, args.n_a, args.n_b)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    plan = {"protocol": dict(PROTOCOL, n_A=args.n_a or PROTOCOL["n_A"],
                             n_B=args.n_b or PROTOCOL["n_B"]),
            "control_cells": control, "confirm_cells": confirm,
            "skipped_witnesses": skipped}
    (OUTDIR / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    n_rand = sum(1 for c in control if "__rand" in c["cell_id"])
    print("control cells: %d (%d stress, %d random)"
          % (len(control), len(control) - n_rand, n_rand))
    print("confirm cells: %d" % len(confirm))
    print("skipped witnesses: %d %s" % (len(skipped), skipped))
    print("control rounds: %d, confirm rounds: %d"
          % (sum(c["rounds"] for c in control), sum(c["rounds"] for c in confirm)))
    print("ETA control: %.2f h, confirm (worst, no early abort): %.2f h"
          % (estimate(control, costs) / 3600, estimate(confirm, costs) / 3600))
    print("\nper control cell (by cost):")
    for c in sorted(control, key=lambda x: -(STARTUP_S + x["rounds"]
                                             * round_cost_s(costs, x["kernel"]))):
        print("  %-30s rounds=%-4d est=%6.0fs shortcut=%s base=%d er=%d rep=%d pos=%s"
              % (c["cell_id"], c["rounds"],
                 STARTUP_S + c["rounds"] * round_cost_s(costs, c["kernel"]),
                 c.get("seed_shortcut"), c["cfg"]["base_seed"],
                 c["cfg"]["equiv_runs"], c["cfg"]["stress_repeats"], c["positions"]))
    return 0


def cmd_run(args):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    logfile = OUTDIR / ("audit_lane%d.log" % args.lane)
    handle = open(OUTDIR / ("audit_lane%d.lock" % args.lane), "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another audit holds the lock -> exit")
        return 0
    handle.seek(0); handle.truncate(); handle.write("%d\n" % os.getpid()); handle.flush()

    b9 = b9_alive()
    if b9 and not args.ignore_b9:
        log("ABORT: B9 lane driver alive %s -- refusing to overlap" % b9, logfile)
        return 3
    if not B9_PAUSE_MARKER.exists() and not args.ignore_b9:
        log("ABORT: %s absent -- the guard could start a lane mid-audit"
            % B9_PAUSE_MARKER, logfile)
        return 4

    os.environ["PATH"] = ("/usr/local/cuda/bin:/root/miniconda3/bin:"
                          "/usr/local/bin:/usr/bin:/bin")
    os.environ["TORCH_EXTENSIONS_DIR"] = str(RUNS / "torch_ext")
    os.environ["MK_GPU_MEMORY_FRACTION"] = "0.92"

    inv = load_inventory()
    costs = json.load(open(COSTS)) if COSTS.exists() else {}
    control, confirm, skipped = build_plan(inv, args.n_a, args.n_b)
    if args.only:
        keep = set(args.only.split(","))
        control = [c for c in control if c["kernel"] in keep]
        confirm = [c for c in confirm if c["kernel"] in keep]
    control = shard(order_cells(control, costs), args.lane, args.lanes)
    confirm = shard(order_cells(confirm, costs), args.lane, args.lanes)
    if args.limit:
        control = control[:args.limit]
        confirm = confirm[:args.limit]

    log("=== audit start pid=%d lane=%d/%d stage=%s control=%d confirm=%d ==="
        % (os.getpid(), args.lane, args.lanes, args.stage,
           len(control), len(confirm)), logfile)
    t0 = time.time()
    if args.stage in ("control", "all"):
        run_cells(control, "control", costs, logfile, force=args.force)
    if args.stage in ("confirm", "all"):
        run_cells(confirm, "confirm", costs, logfile, force=args.force)
    log("=== audit stage done in %.1f min ===" % ((time.time() - t0) / 60), logfile)
    (OUTDIR / ("STAGE_DONE_%s_lane%d" % (args.stage, args.lane))).write_text(
        datetime.now().isoformat(), encoding="utf-8")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--n-a", type=int, default=None)
    p.add_argument("--n-b", type=int, default=None); p.set_defaults(fn=cmd_plan)
    r = sub.add_parser("run")
    r.add_argument("--stage", choices=("control", "confirm", "all"), default="control")
    r.add_argument("--n-a", type=int, default=None)
    r.add_argument("--n-b", type=int, default=None)
    r.add_argument("--only", default=None)
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--force", action="store_true")
    r.add_argument("--ignore-b9", action="store_true")
    r.add_argument("--lane", type=int, default=0)
    r.add_argument("--lanes", type=int, default=1)
    r.set_defaults(fn=cmd_run)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
