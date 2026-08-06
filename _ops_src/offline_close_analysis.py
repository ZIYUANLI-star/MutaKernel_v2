#!/usr/bin/env python3
"""Offline close-of-campaign analyses (CPU only, run after lanes close).

Subcommands
  power      §5.1.5 preregistered power analysis for the all-PASS audit
             stratum: per-stratum sample size n such that, when the true
             joint miss rate is at least P0 (default 5%), at least one
             jointly-missed defect appears in the sample with probability
             at least POWER (default 95%).  Exact hypergeometric with
             finite-population correction per stratum (corpus x language x
             task level).  Also emits the audit time-limit design constant
             (30 min/kernel, preregistered).
  equaltime  Table 8a/8b equal-time truncation: per strategy row, walk each
             subject's cases in ledger order accumulating per-case wallclock
             and record time-to-first-detection; emit coverage-at-budget
             curves on a shared time grid plus coverage at the M-full median
             row time (the equal-time anchor).
  fidelity   merge the three port reproduction-deviation summaries
             (B7/B8 from run_port_fidelity.py, B9 from b9-aggregate).

All outputs are JSON; inputs are the append-only lane ledgers.  Nothing here
mutates any ledger.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

P0_DEFAULT = 0.05
POWER_DEFAULT = 0.95
AUDIT_MINUTES_PER_KERNEL = 30  # design constant, preregistered


def now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- power
def _min_n_hypergeom(N: int, p0: float, power: float) -> int:
    """Smallest n with P(X >= 1) >= power when K = ceil(p0*N) defectives
    exist in a population of N (sampling without replacement)."""
    if N <= 0:
        return 0
    K = max(1, math.ceil(p0 * N))
    # P(X = 0) = C(N-K, n) / C(N, n); iterate n upward.
    for n in range(1, N + 1):
        log_p0 = 0.0
        impossible = False
        for i in range(n):
            num = N - K - i
            den = N - i
            if num <= 0:
                impossible = True
                break
            log_p0 += math.log(num) - math.log(den)
        if impossible or 1.0 - math.exp(log_p0) >= power:
            return n
    return N


def cmd_power(args):
    # subjects: manifest(s) -> subject_id -> stratum
    stratum_of = {}
    for mpath in args.subjects:
        m = json.loads(Path(mpath).read_text("utf-8"))
        for s in m["subjects"]:
            sid = s["subject_id"]
            corpus = s.get("dataset") or sid.split("__")[0]
            lang = s.get("language", "cuda")
            task = s.get("task_id") or sid.split("__")[1]
            level = task.split("_P")[0]  # e.g. KB_L1
            stratum_of[sid] = (corpus, lang, level)

    # ledgers: any FAIL (killed=True) marks the subject as alarmed
    alarmed = set()
    seen = set()
    for lpath in args.ledgers:
        p = Path(lpath)
        if not p.exists():
            print(f"WARNING ledger missing: {p}")
            continue
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                sid = rec.get("subject_id")
                if sid not in stratum_of:
                    continue
                seen.add(sid)
                wr = rec.get("worker_result") or {}
                if wr.get("killed") is True:
                    alarmed.add(sid)

    all_pass = sorted(set(stratum_of) & seen - alarmed)
    by_stratum = defaultdict(list)
    for sid in all_pass:
        by_stratum[stratum_of[sid]].append(sid)

    strata = {}
    total_n = 0
    for key in sorted(by_stratum):
        N = len(by_stratum[key])
        n = _min_n_hypergeom(N, args.p0, args.power)
        total_n += n
        strata["__".join(key)] = {
            "population_all_pass": N,
            "sample_n": n,
            "inclusion_probability": round(n / N, 6) if N else None,
        }

    out = {
        "design_constants": {
            "joint_miss_rate_threshold_p0": args.p0,
            "power": args.power,
            "audit_minutes_per_kernel": AUDIT_MINUTES_PER_KERNEL,
            "estimators": "Horvitz-Thompson and Hajek, side by side",
            "sampling": "stratified SRSWOR, strata = corpus x language x "
                        "task level, exact hypergeometric FPC per stratum",
        },
        "subjects_total": len(stratum_of),
        "subjects_observed": len(seen),
        "subjects_alarmed": len(alarmed),
        "subjects_all_pass": len(all_pass),
        "strata": strata,
        "total_sample_n": total_n,
        "generated_at": now(),
        "ledgers": [str(x) for x in args.ledgers],
    }
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in
                      ("subjects_all_pass", "total_sample_n")}, indent=1))
    print("written:", args.out)


# ------------------------------------------------------------- equaltime
def cmd_equaltime(args):
    # per (strategy, subject): ordered case walls + first-detection time
    rows = defaultdict(lambda: defaultdict(list))
    for lpath in args.ledgers:
        p = Path(lpath)
        if not p.exists():
            print(f"WARNING ledger missing: {p}")
            continue
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                strat = rec.get("strategy_name")
                sid = rec.get("subject_id")
                wr = rec.get("worker_result") or {}
                t = wr.get("timings_ms") or {}
                wall = t.get("total_ms") or t.get("wall_ms") or 0.0
                rows[strat][sid].append(
                    (float(wall) / 1000.0, wr.get("killed") is True))

    per_row = {}
    for strat, subj in rows.items():
        detect_t, total_t = {}, {}
        for sid, cases in subj.items():
            acc = 0.0
            first = None
            for wall, killed in cases:
                acc += wall
                if killed and first is None:
                    first = acc
            detect_t[sid] = first
            total_t[sid] = acc
        per_row[strat] = {"detect_t": detect_t, "total_t": total_t}

    anchor_row = args.anchor
    anchor_times = sorted(
        per_row.get(anchor_row, {}).get("total_t", {}).values())
    anchor_median = (anchor_times[len(anchor_times) // 2]
                     if anchor_times else None)

    grid = [x * (anchor_median or 60.0) / 20.0 for x in range(1, 41)] \
        if anchor_median else []
    curves = {}
    for strat, d in per_row.items():
        ts = d["detect_t"]
        n = len(d["total_t"])
        curve = []
        for g in grid:
            det = sum(1 for v in ts.values() if v is not None and v <= g)
            curve.append({"t_s": round(g, 2), "detected": det,
                          "fraction": round(det / n, 4) if n else None})
        at_anchor = sum(1 for v in ts.values()
                        if v is not None and v <= (anchor_median or 0))
        curves[strat] = {
            "subjects": n,
            "detected_total": sum(1 for v in ts.values() if v is not None),
            "detected_at_anchor_budget": at_anchor,
            "curve": curve,
        }

    out = {
        "anchor_row": anchor_row,
        "anchor_median_row_time_s": anchor_median,
        "rows": curves,
        "generated_at": now(),
        "ledgers": [str(x) for x in args.ledgers],
        "note": "per-case wallclock from worker timings; detection time = "
                "cumulative wall at first FAIL in ledger order",
    }
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("written:", args.out)


# -------------------------------------------------------------- fidelity
def cmd_fidelity(args):
    merged = {"generated_at": now()}
    for tag, path in (("b7", args.b7), ("b8", args.b8), ("b9", args.b9)):
        p = Path(path)
        merged[tag] = (json.loads(p.read_text("utf-8"))
                       if p.exists() else {"missing": str(p)})
    Path(args.out).write_text(json.dumps(merged, indent=2), encoding="utf-8")
    devs = {t: merged[t].get("reproduction_deviation")
            for t in ("b7", "b8", "b9")}
    print(json.dumps({"reproduction_deviation": devs}))
    print("written:", args.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("power")
    p.add_argument("--subjects", nargs="+", required=True)
    p.add_argument("--ledgers", nargs="+", required=True)
    p.add_argument("--p0", type=float, default=P0_DEFAULT)
    p.add_argument("--power", type=float, default=POWER_DEFAULT)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_power)

    p = sub.add_parser("equaltime")
    p.add_argument("--ledgers", nargs="+", required=True)
    p.add_argument("--anchor", default="mutakernel-full")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_equaltime)

    p = sub.add_parser("fidelity")
    p.add_argument("--b7", required=True)
    p.add_argument("--b8", required=True)
    p.add_argument("--b9", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_fidelity)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
