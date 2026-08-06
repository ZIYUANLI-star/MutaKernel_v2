#!/usr/bin/env python3
"""Build the B9 calibration resume queue (post torch.quantile fix).

Deployed to /root/mk_v2/_b9_resume_prep.py.

``--dry-run`` (default) only reads and prints: what is kept, what is requeued,
the host-memory budget per unit and an ETA simulation for 1 and 2 lanes.
``--commit`` additionally archives the pre-fix records verbatim and writes
queue_state.json, which is the only file the lane drivers mutate.

Resume rules
------------
kept, never re-run   calibrated_ok, calibrated_heavy_tail, controls_incomplete
                     (real calibration outcomes: a rerun reproduces them)
requeued             run_error, control_timeout, driver_exception
                     (the 10 torch.quantile crashes and the 3 SIGKILLs)
never started        no row yet

The pre-fix calibration_lane*.jsonl / completed_lane*.json are copied into
archive/pre_quantile_fix_<ts>/ and left in place; nothing is deleted or
rewritten.  New rows land in calibration_v2_lane{N}.jsonl, so an aggregation
step can prefer the v2 row for any unit that appears in both.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

OUT_ROOT = Path("/root/mk_v2_runs/e3_b9_calib")
KEEP_STATUSES = ("calibrated_ok", "calibrated_heavy_tail", "controls_incomplete")
REQUEUE_STATUSES = ("run_error", "control_timeout", "driver_exception")

# error_stats host high-water, measured on this box (probe: 34.0 B per output
# element, stable from 1.7e7 to 2.0e8 elements)
CMP_BYTES_PER_ELEM = 34.0
# reservations are the estimate times this factor (the L1_P8 end-to-end check
# measured 2.11GB against a 1.9GB estimate)
MEMORY_SAFETY_FACTOR = 1.3
GIB = float(1 << 30)

# ETA model.  Anchors from the 15 calibrated_ok units of the 16:38 run:
#   median 163s/unit, slowest 319s/unit, all with <=5.0e7 (in+out) elements.
# The two rates bracket the two regimes we have measured:
#   ELEMENTWISE_RATE  error_stats throughput, 2.0e8 elements in 5.1s
#   MATMUL_RATE       the slowest observed unit (L1_P1 f32: 5.0e7 elements
#                     per case in 7.49s, fp64 CPU matmul bound)
ELEMENTWISE_RATE = 3.9e7
MATMUL_RATE = 6.7e6
CASES_PER_UNIT = 32
FLOOR_WALL_S = 100.0


def load_rows():
    """Last recorded row per unit; v2 waves supersede v1."""
    rows = {}
    for path in (sorted(OUT_ROOT.glob("calibration_lane*.jsonl"))
                 + sorted(OUT_ROOT.glob("calibration_v2_lane*.jsonl"))):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                row["_source"] = path.name
                rows[row["unit"]] = row
    return rows


def estimate(subject, dtype):
    in_numel = subject.get("in_numel") or 0
    out_numel = subject.get("out_numel") or 0
    itemsize = 4 if dtype == "float32" else 2
    reference_stage = 8.0 * (in_numel + out_numel) + itemsize * out_numel
    comparison_stage = (CMP_BYTES_PER_ELEM + 2.0 * itemsize) * out_numel
    peak_gb = max(reference_stage, comparison_stage) / GIB
    elements = in_numel + out_numel
    fast = max(FLOOR_WALL_S, CASES_PER_UNIT * elements / ELEMENTWISE_RATE)
    slow = max(FLOOR_WALL_S, CASES_PER_UNIT * elements / MATMUL_RATE)
    return {
        "out_numel": out_numel,
        "in_numel": in_numel,
        "est_peak_gb": round(peak_gb, 2),
        "reserve_gb": round(peak_gb * MEMORY_SAFETY_FACTOR, 2),
        "est_wall_s_fast": round(fast),
        "est_wall_s_slow": round(slow),
        "unit_timeout_s": int(min(14400, max(3600, 4 * slow))),
        "above_quantile_limit": out_numel > 2 ** 24,
    }


def build(order):
    table = json.loads((OUT_ROOT / "task_table.json").read_text(encoding="utf-8"))
    sizes = json.loads((OUT_ROOT / "unit_size_table.json").read_text(encoding="utf-8"))
    by_key = {s["task_key"]: s for s in sizes["subjects"]}
    rows = load_rows()

    kept, requeued, fresh = [], [], []
    for subject in table["tasks"]:
        for dtype in subject["dtypes"]:
            uid = f"{subject['task_key']}__{dtype}"
            unit = {
                "unit": uid,
                "task_key": subject["task_key"],
                "dtype": dtype,
                "task_file": subject["file"],
                "reduction_heavy": subject["reduction_heavy"],
            }
            unit.update(estimate(by_key.get(subject["task_key"], {}), dtype))
            row = rows.get(uid)
            status = row.get("control_status") if row else None
            unit["previous_status"] = status
            if status in KEEP_STATUSES:
                kept.append(unit)
            elif status is None:
                fresh.append(unit)
            else:
                unit["previous_row"] = row
                requeued.append(unit)

    queue = requeued + fresh
    if order == "asc":
        queue.sort(key=lambda u: u["est_peak_gb"])
    elif order == "desc":
        queue.sort(key=lambda u: -u["est_peak_gb"])
    return kept, requeued, fresh, queue


def simulate(queue, lanes, budget_gb, rate_key):
    """First-fit admission against the memory budget, mirroring the driver."""
    pending = [dict(u) for u in queue]
    running = []
    clock = 0.0
    while pending or running:
        while len(running) < lanes and pending:
            used = sum(gb for _, gb in running)
            pick = None
            for index, unit in enumerate(pending):
                if not running or used + unit["reserve_gb"] <= budget_gb:
                    pick = index
                    break
            if pick is None:
                break
            unit = pending.pop(pick)
            running.append((clock + unit[rate_key], unit["reserve_gb"]))
        if not running:
            break
        running.sort()
        clock, _ = running.pop(0)
    return clock


def human(seconds):
    return "%.1f h (%.0f min)" % (seconds / 3600.0, seconds / 60.0)


def report(kept, requeued, fresh, queue, budget_gb, lanes_options):
    print("=== resume plan ===")
    print("kept (never re-run): %d units" % len(kept))
    counts = {}
    for unit in kept:
        counts[unit["previous_status"]] = counts.get(unit["previous_status"], 0) + 1
    for status, count in sorted(counts.items()):
        print("    %-24s %d" % (status, count))
    print("requeued (previous attempt failed): %d units" % len(requeued))
    for unit in requeued:
        row = unit["previous_row"]
        print("    %-22s %-18s exit=%-4s out_numel=%-12d est_peak=%5.1fGB  %s"
              % (unit["unit"], row.get("control_status"), row.get("exit_code"),
                 unit["out_numel"], unit["est_peak_gb"],
                 "quantile-limit crash" if unit["out_numel"] > 2 ** 24
                 and row.get("exit_code") == 1 else
                 "SIGKILL (host OOM)" if row.get("exit_code") == -9 else ""))
    print("never started: %d units" % len(fresh))
    print("queue length: %d units" % len(queue))
    print("units above the torch.quantile limit (2**24) in the queue: %d"
          % sum(1 for u in queue if u["above_quantile_limit"]))

    print()
    print("=== host memory budget (reservation = estimate x %.1f) ===" % MEMORY_SAFETY_FACTOR)
    print("budget %.0f GiB of the 120 GiB cgroup; a unit whose reservation "
          "exceeds the budget still runs, but strictly alone" % budget_gb)
    buckets = [(0, 5), (5, 15), (15, 30), (30, 60), (60, 90), (90, 1e9)]
    for low, high in buckets:
        members = [u for u in queue if low <= u["reserve_gb"] < high]
        if members:
            print("    reserve [%3g,%4g) GiB : %3d units   max_pairable=%s"
                  % (low, high, len(members),
                     "yes" if high <= budget_gb / 2 else "one-at-a-time"))
    biggest = sorted(queue, key=lambda u: -u["reserve_gb"])[:6]
    for unit in biggest:
        print("    biggest: %-22s reserve=%5.1f GiB (out_numel=%d)"
              % (unit["unit"], unit["reserve_gb"], unit["out_numel"]))

    print()
    print("=== ETA (first-fit admission simulation) ===")
    print("model: per unit = 32 cases x (in+out elements) / rate, floor %ds;"
          % FLOOR_WALL_S)
    print("       fast rate %.2g elem/s (measured error_stats throughput),"
          % ELEMENTWISE_RATE)
    print("       slow rate %.2g elem/s (slowest observed unit, fp64 matmul bound)"
          % MATMUL_RATE)
    requeued_prefix = [u for u in queue if u["previous_status"] in REQUEUE_STATUSES]
    for label, subset in (("whole queue", queue),
                          ("first wave: the %d requeued units only"
                           % len(requeued_prefix), requeued_prefix)):
        if not subset:
            continue
        print("    %s" % label)
        for lanes in lanes_options:
            fast = simulate(subset, lanes, budget_gb, "est_wall_s_fast")
            slow = simulate(subset, lanes, budget_gb, "est_wall_s_slow")
            print("        %d lane(s): %s  ..  %s" % (lanes, human(fast), human(slow)))
    print("    caution: no unit above 5e7 elements has ever completed, so the")
    print("    upper end is an extrapolation, not a measurement.")


def commit(kept, requeued, queue):
    stamp = time.strftime("%Y%m%dT%H%M%S")
    archive = OUT_ROOT / "archive" / ("pre_quantile_fix_" + stamp)
    archive.mkdir(parents=True, exist_ok=True)
    copied = []
    for pattern in ("calibration_lane*.jsonl", "completed_lane*.json",
                    "calibration_v2_lane*.jsonl", "completed_v2_lane*.json",
                    "lane*.log", "guard_b9.log", "run_manifest.json"):
        for path in sorted(OUT_ROOT.glob(pattern)):
            shutil.copy2(path, archive / path.name)
            copied.append(path.name)
    (archive / "requeued_units.json").write_text(json.dumps({
        "archived_at": stamp,
        "reason": ("torch.quantile numel-limit fix + error_stats memory rewrite; "
                   "these units produced no calibration result and are re-queued"),
        "kept_statuses": list(KEEP_STATUSES),
        "requeued": [{"unit": u["unit"], "previous_row": u["previous_row"]}
                     for u in requeued],
    }, indent=2), encoding="utf-8")
    print("archived %d files (verbatim copies, originals untouched) -> %s"
          % (len(copied), archive))

    state_path = OUT_ROOT / "queue_state.json"
    if state_path.is_file():
        shutil.copy2(state_path, archive / "queue_state.json.previous")
    state_path.write_text(json.dumps({
        "created_at": stamp,
        "wave": "v2_post_quantile_fix",
        "pending": [u["unit"] for u in queue],
        "claimed": {},
        "done": {u["unit"]: u["previous_status"] for u in kept},
        "units": {u["unit"]: u for u in queue},
    }, indent=2), encoding="utf-8")
    print("wrote %s (%d pending, %d already done)"
          % (state_path, len(queue), len(kept)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true",
                        help="archive the pre-fix records and write queue_state.json")
    parser.add_argument("--order", choices=["table", "asc", "desc"], default="table")
    parser.add_argument("--budget-gb", type=float, default=100.0)
    parser.add_argument("--limit", type=int, default=0,
                        help="keep only the first N queue entries (pilot runs)")
    args = parser.parse_args()

    kept, requeued, fresh, queue = build(args.order)
    if args.limit:
        queue = queue[:args.limit]
    report(kept, requeued, fresh, queue, args.budget_gb, (1, 2))
    print()
    if args.commit:
        commit(kept, requeued, queue)
        print("PREP_COMMITTED")
    else:
        print("PREP_DRY_RUN (nothing written)")


if __name__ == "__main__":
    main()
