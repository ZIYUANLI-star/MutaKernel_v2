#!/usr/bin/env python3
"""Aggregate the B9 control-calibration rows into the E3 tolerance ledger.

Deployed to /root/mk_v2/_b9_aggregate.py.  Read-only over
/root/mk_v2_runs/e3_b9_calib except for its own two output files.

Why this script exists rather than a paragraph in a report
----------------------------------------------------------
The lane driver writes ``control_status = controls_incomplete`` whenever the 32
control executions do not yield 32 finite error samples.  That single name
covers two situations that must never be counted together:

  * **the protocol cannot decide the subject at all** -- the *correct* fp64
    reference itself overflows, so no finite error sample exists and no
    tolerance can be calibrated.  Observed on fp16 subjects with very large
    reductions (L1_P6 float16: all 32 controls return Inf).  Per decision 5 of
    the calibration ruling these units are reported as "undecidable under the
    ported protocol": they stay in every comparison-table denominator and B9 is
    never credited with a detection on them.  Dropping them would shrink B9's
    denominator and inflate its precision and recall -- the mirror image of the
    ``NO_DEFECT_FOUND != correct`` error we charge the baseline with in RQ1.
  * **anything else** -- a partial control batch, a mixed outcome set, a shape
    mismatch.  These are *not* a protocol limit and must not be laundered into
    the undecidable ledger; they are open items that need a rerun or a look.

The distinction is therefore computed here, from the recorded
``outcome_kinds``, and asserted by ``--self-test``, so that no later statistic
can silently inherit the ambiguous name.

Criterion (blueprint supplement E3_B9校准决定与限制说明.md section 7)
-------------------------------------------------------------------
    outcome_kinds == {"inf": cases}   -> protocol_undecidable_overflow
    outcome_kinds == {"nan": cases}   -> protocol_undecidable_nan
    otherwise                         -> controls_incomplete_unresolved

Both undecidable kinds require the *whole* control batch to be non-finite: one
finite sample among Infs means the reference did not uniformly overflow, which
is an anomaly to inspect rather than a protocol boundary.

The same pass also splits ``run_error`` by exit code, because a SIGKILL (host
OOM) is the resource boundary of decision 3 / section 8 while a non-zero exit
is a code-level failure, and the two carry different reporting obligations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

OUT_ROOT = Path("/root/mk_v2_runs/e3_b9_calib")

CALIBRATED = ("calibrated_ok", "calibrated_heavy_tail")
UNDECIDABLE = ("protocol_undecidable_overflow", "protocol_undecidable_nan")
# reservation = estimate x this factor; a measured ratio above it means the
# 34 B/output-element model under-predicts and the admission gate is unsafe
MEMORY_SAFETY_FACTOR = 1.3


def refine_status(row: dict) -> tuple[str, str]:
    """Map a recorded row onto a reason-bearing status.

    Returns ``(status, why)``.  ``why`` is a short human-readable reason kept
    with the row so the ledger can be read without re-deriving the rule.
    """
    status = row.get("control_status")
    if status == "controls_incomplete":
        kinds = row.get("outcome_kinds") or {}
        cases = row.get("cases")
        total = sum(kinds.values()) if kinds else 0
        if cases is not None and total != cases:
            return ("controls_incomplete_unresolved",
                    "outcome_kinds sum %d != cases %d" % (total, cases))
        if set(kinds) == {"inf"} and total > 0:
            return ("protocol_undecidable_overflow",
                    "all %d controls returned Inf: the fp64 reference itself "
                    "overflows in this dtype, so no finite error sample exists"
                    % total)
        if set(kinds) == {"nan"} and total > 0:
            return ("protocol_undecidable_nan",
                    "all %d controls returned NaN: no finite error sample "
                    "exists" % total)
        return ("controls_incomplete_unresolved",
                "outcome_kinds=%s (not a uniform non-finite batch)"
                % json.dumps(kinds, sort_keys=True))
    if status == "run_error":
        exit_code = row.get("exit_code")
        if exit_code == -9:
            return ("run_error_host_oom",
                    "SIGKILL: host OOM; resource boundary of the port, not a "
                    "verdict")
        return ("run_error_crash", "non-zero exit %s" % exit_code)
    return (status, "")


def load_rows(out_root: Path) -> dict:
    """Last recorded row per unit; v2 waves supersede v1 (same rule as prep)."""
    rows = {}
    for path in (sorted(out_root.glob("calibration_lane*.jsonl"))
                 + sorted(out_root.glob("calibration_v2_lane*.jsonl"))):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            row["_source"] = path.name
            rows[row["unit"]] = row
    return rows


def heavy_tail_evidence(rows: dict) -> dict:
    """The section 6 fragility measurement, recomputed from the rows."""
    calibrated = [r for r in rows.values()
                  if r.get("control_status") in CALIBRATED]
    fp16 = [r for r in calibrated if r["dtype"] == "float16"]
    fp32 = [r for r in calibrated if r["dtype"] == "float32"]

    def tail(subset):
        return [r for r in subset
                if r["control_status"] == "calibrated_heavy_tail"]

    ratios = {}
    for row in tail(calibrated):
        tol = row.get("calibrated_tol")
        top = row.get("control_max_abs")
        if tol:
            ratios[row["unit"]] = round(top / tol, 6)
    return {
        "calibrated_units": len(calibrated),
        "heavy_tail_units": len(tail(calibrated)),
        "heavy_tail_units_fp16": len(tail(fp16)),
        "heavy_tail_units_fp32": len(tail(fp32)),
        "calibrated_units_fp16": len(fp16),
        "calibrated_units_fp32": len(fp32),
        "max_over_tol_ratio": ratios,
        "note": ("rates are sample-dependent and grow with the calibration "
                 "run; the invariant is max/tol = 4/3 whenever a p95 grid "
                 "point is followed by the next fp16 grid point (1.5 < 2)"),
    }


def memory_model_check(rows: dict) -> dict:
    """Measured peak RSS against the 34 B/output-element estimate."""
    pairs = []
    for row in rows.values():
        est = row.get("est_peak_gb")
        act = row.get("unit_peak_rss_gb")
        if est and act:
            pairs.append((row["unit"], act / est, est, act))
    pairs.sort(key=lambda p: p[1])
    over = [p for p in pairs if p[1] > MEMORY_SAFETY_FACTOR]
    return {
        "n": len(pairs),
        "min_ratio": round(pairs[0][1], 3) if pairs else None,
        "median_ratio": round(pairs[len(pairs) // 2][1], 3) if pairs else None,
        "max_ratio": round(pairs[-1][1], 3) if pairs else None,
        "over_safety_factor": [
            {"unit": u, "ratio": round(r, 3), "est_peak_gb": e,
             "unit_peak_rss_gb": a} for u, r, e, a in over],
        "safety_factor": MEMORY_SAFETY_FACTOR,
        "per_unit": [{"unit": u, "ratio": round(r, 3), "est_peak_gb": e,
                      "unit_peak_rss_gb": a} for u, r, e, a in pairs],
    }


def aggregate(out_root: Path) -> dict:
    rows = load_rows(out_root)
    counts, ledger, tolerances = {}, [], {}
    for unit in sorted(rows):
        row = rows[unit]
        status, why = refine_status(row)
        counts[status] = counts.get(status, 0) + 1
        entry = {
            "unit": unit,
            "task_key": row.get("task_key"),
            "dtype": row.get("dtype"),
            "recorded_status": row.get("control_status"),
            "status": status,
            "why": why,
            "exit_code": row.get("exit_code"),
            "cases": row.get("cases"),
            "outcome_kinds": row.get("outcome_kinds"),
            "est_peak_gb": row.get("est_peak_gb"),
            "unit_peak_rss_gb": row.get("unit_peak_rss_gb"),
            "wall_s": row.get("wall_s"),
            "source": row.get("_source"),
        }
        if status in CALIBRATED:
            entry["calibrated_tol"] = row.get("calibrated_tol")
            entry["control_max_abs"] = row.get("control_max_abs")
            tolerances[unit] = {
                "task_key": row.get("task_key"),
                "dtype": row.get("dtype"),
                "calibrated_tol": row.get("calibrated_tol"),
                "control_max_abs": row.get("control_max_abs"),
                "control_pass_rate_at_tol": row.get("control_pass_rate_at_tol"),
                "heavy_tail": row["control_status"] == "calibrated_heavy_tail",
            }
        ledger.append(entry)

    undecidable = [e for e in ledger if e["status"] in UNDECIDABLE]
    oom = [e for e in ledger if e["status"] == "run_error_host_oom"]
    unresolved = [e for e in ledger
                  if e["status"] in ("controls_incomplete_unresolved",
                                     "run_error_crash", "control_timeout",
                                     "driver_exception")]
    return {
        "generated_from": str(out_root),
        "rows": len(rows),
        "status_counts": counts,
        "calibrated_units": len(tolerances),
        "undecidable_units": [
            {k: e[k] for k in ("unit", "task_key", "dtype", "status", "why")}
            for e in undecidable],
        "host_oom_units": [
            {k: e[k] for k in ("unit", "est_peak_gb", "unit_peak_rss_gb",
                               "exit_code")} for e in oom],
        "unresolved_units": [
            {k: e[k] for k in ("unit", "status", "why", "exit_code")}
            for e in unresolved],
        "heavy_tail_evidence": heavy_tail_evidence(rows),
        "memory_model": memory_model_check(rows),
        "reporting_rules": {
            "undecidable": ("counted in every comparison-table denominator; "
                            "B9 is never credited with a detection on them "
                            "(calibration ruling decision 5, section 7)"),
            "host_oom": ("resource boundary of the port under the 120 GiB host "
                         "budget; same denominator treatment as undecidable "
                         "units (decision 3, section 8)"),
            "unresolved": ("neither a protocol nor a resource boundary: must be "
                           "rerun or explained before the ledger is final"),
        },
        "ledger": ledger,
    }


SELF_TEST_CASES = [
    ({"control_status": "controls_incomplete", "cases": 32,
      "outcome_kinds": {"inf": 32}}, "protocol_undecidable_overflow"),
    ({"control_status": "controls_incomplete", "cases": 32,
      "outcome_kinds": {"nan": 32}}, "protocol_undecidable_nan"),
    # one finite sample among Infs is an anomaly, not a protocol boundary
    ({"control_status": "controls_incomplete", "cases": 32,
      "outcome_kinds": {"inf": 31, "pass": 1}},
     "controls_incomplete_unresolved"),
    ({"control_status": "controls_incomplete", "cases": 32,
      "outcome_kinds": {"inf": 30, "nan": 2}},
     "controls_incomplete_unresolved"),
    # a short batch is never undecidable even if uniformly Inf
    ({"control_status": "controls_incomplete", "cases": 32,
      "outcome_kinds": {"inf": 12}}, "controls_incomplete_unresolved"),
    ({"control_status": "controls_incomplete", "cases": 32,
      "outcome_kinds": {}}, "controls_incomplete_unresolved"),
    ({"control_status": "run_error", "exit_code": -9}, "run_error_host_oom"),
    ({"control_status": "run_error", "exit_code": 1}, "run_error_crash"),
    ({"control_status": "calibrated_ok"}, "calibrated_ok"),
    ({"control_status": "calibrated_heavy_tail"}, "calibrated_heavy_tail"),
    ({"control_status": "control_timeout"}, "control_timeout"),
]


def self_test() -> int:
    bad = 0
    for row, expected in SELF_TEST_CASES:
        got, why = refine_status(row)
        flag = "ok " if got == expected else "FAIL"
        if got != expected:
            bad += 1
        print("  [%s] %-46s -> %-32s %s"
              % (flag, json.dumps(row, sort_keys=True), got, why[:60]))
    print("SELF_TEST_%s (%d cases, %d failures)"
          % ("FAILED" if bad else "OK", len(SELF_TEST_CASES), bad))
    return 1 if bad else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--write", action="store_true",
                        help="write the summary and tolerance files")
    args = parser.parse_args()

    print("=== B9 calibration aggregation ===")
    print("criterion self-test:")
    if self_test():
        return 1
    if args.self_test:
        return 0

    summary = aggregate(args.out_root)
    print()
    print("rows: %d" % summary["rows"])
    print("status counts:")
    for status, count in sorted(summary["status_counts"].items()):
        print("   %-34s %d" % (status, count))
    print("calibrated units (tolerance available): %d"
          % summary["calibrated_units"])
    print("undecidable under the ported protocol: %d"
          % len(summary["undecidable_units"]))
    for entry in summary["undecidable_units"]:
        print("   %-24s %-28s %s" % (entry["unit"], entry["status"],
                                     entry["why"][:80]))
    print("host-OOM (resource boundary): %d" % len(summary["host_oom_units"]))
    for entry in summary["host_oom_units"]:
        print("   %-24s est=%.1f GB peak=%.1f GB exit=%s"
              % (entry["unit"], entry["est_peak_gb"] or 0,
                 entry["unit_peak_rss_gb"] or 0, entry["exit_code"]))
    print("unresolved (needs a rerun or an explanation): %d"
          % len(summary["unresolved_units"]))
    for entry in summary["unresolved_units"]:
        print("   %-24s %-32s %s" % (entry["unit"], entry["status"],
                                     entry["why"][:70]))
    evidence = summary["heavy_tail_evidence"]
    print("heavy-tail evidence: %d/%d calibrated units (fp16 %d/%d, fp32 %d/%d)"
          % (evidence["heavy_tail_units"], evidence["calibrated_units"],
             evidence["heavy_tail_units_fp16"], evidence["calibrated_units_fp16"],
             evidence["heavy_tail_units_fp32"], evidence["calibrated_units_fp32"]))
    for unit, ratio in sorted(evidence["max_over_tol_ratio"].items()):
        print("   %-24s max/tol = %.6f" % (unit, ratio))
    memory = summary["memory_model"]
    print("memory model actual/estimate: n=%s min=%s median=%s max=%s "
          "(safety factor %.1f)"
          % (memory["n"], memory["min_ratio"], memory["median_ratio"],
             memory["max_ratio"], memory["safety_factor"]))
    for entry in memory["over_safety_factor"]:
        print("   OVER SAFETY FACTOR %-22s ratio=%.3f est=%.1f peak=%.1f"
              % (entry["unit"], entry["ratio"], entry["est_peak_gb"],
                 entry["unit_peak_rss_gb"]))

    if args.write:
        summary_path = args.out_root / "b9_calibration_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True),
                                encoding="utf-8")
        tolerances = {
            unit: entry for unit, entry in (
                (e["unit"], {"task_key": e["task_key"], "dtype": e["dtype"],
                             "calibrated_tol": e.get("calibrated_tol"),
                             "control_max_abs": e.get("control_max_abs"),
                             "heavy_tail":
                                 e["status"] == "calibrated_heavy_tail"})
                for e in summary["ledger"] if e["status"] in CALIBRATED)}
        tol_path = args.out_root / "b9_calibrated_tolerances.json"
        tol_path.write_text(json.dumps({
            "tolerances": tolerances,
            "undecidable": summary["undecidable_units"],
            "host_oom": summary["host_oom_units"],
            "denominator_rule": summary["reporting_rules"],
        }, indent=2, sort_keys=True), encoding="utf-8")
        print("\nwrote %s\nwrote %s" % (summary_path, tol_path))
    else:
        print("\n(read-only; pass --write to persist the summary)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
