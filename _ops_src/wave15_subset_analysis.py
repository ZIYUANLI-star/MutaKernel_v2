#!/usr/bin/env python3
"""Derive wave-1.5 lane subject subsets from a closed Lane M ledger.

Reuse rules (preregistered, see design doc):

* Lane G (legacy oracle).  The legacy tolerance (flat 1e-2) is strictly no
  tighter than the unified dtype-aware oracle in every dtype (fp32 1e-4 ->
  1e-2 looser; fp16/bf16 identical 1e-2).  Hence PASS verdicts carry over,
  crash/INCONCLUSIVE verdicts are oracle-independent, and only subjects with
  at least one FAIL under the unified oracle can change verdict.  Lane G
  re-executes the full anchor / mutakernel-full rows on exactly those
  subjects; every other subject's legacy-row result is copied at analysis
  level with rule tag ``oracle-monotonic-carryover``.
* Lane L (LODO).  Subjects with no mutakernel-full FAIL have complete
  retained-case results in Lane M (all executed); the delta rows (replacement
  cases only) suffice -> subset A.  Subjects with a mutakernel-full FAIL have
  early-stop-truncated retained results, so the full LODO rows re-execute
  -> subset B (early-stop re-truncates them cheaply).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--observations", required=True, type=Path)
    ap.add_argument("--subjects", required=True, type=Path,
                    help="wave subject manifest (for the full id universe)")
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()

    manifest = json.loads(args.subjects.read_text(encoding="utf-8"))
    universe = sorted(s["subject_id"] for s in manifest["subjects"])
    universe_set = set(universe)

    fails = defaultdict(set)   # strategy_name -> set(subject_id)
    seen_rows = defaultdict(set)
    with open(args.observations, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            sid = rec.get("subject_id")
            strat = rec.get("strategy_name")
            if sid not in universe_set:
                continue
            seen_rows[strat].add(sid)
            wr = rec.get("worker_result") or {}
            if wr.get("killed") is True:
                fails[strat].add(sid)

    anchor_detected = sorted(fails.get("five-iid-historical-anchor", set()))
    mfull_detected = sorted(fails.get("mutakernel-full", set()))
    mfull_nondetected = sorted(universe_set - set(mfull_detected))
    lane_g = sorted(set(anchor_detected) | set(mfull_detected))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "lane_g_subjects.txt": lane_g,
        "lane_lb_subjects.txt": mfull_detected,
        "lane_la_subjects.txt": mfull_nondetected,
        "anchor_detected.txt": anchor_detected,
    }
    for name, ids in outputs.items():
        (args.out_dir / name).write_text(
            "\n".join(ids) + ("\n" if ids else ""), encoding="utf-8")

    report = {
        "universe": len(universe),
        "strategy_row_coverage": {k: len(v) for k, v in sorted(seen_rows.items())},
        "detected_by_row": {k: len(v) for k, v in sorted(fails.items())},
        "lane_g_subjects": len(lane_g),
        "lane_la_subjects": len(mfull_nondetected),
        "lane_lb_subjects": len(mfull_detected),
        "reuse_rules": [
            "oracle-monotonic-carryover (Lane G non-members)",
            "retained-case-result-reuse (Lane L subset A)",
        ],
    }
    (args.out_dir / "subset_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
