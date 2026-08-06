#!/usr/bin/env python3
"""Build the B9 per-(task,dtype) calibrated-tolerance map from the closed
calibration ledgers (dedup rule mirrors b9_calib_final_summary: latest
finished_at wins across calibration*.jsonl)."""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calib-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    latest = {}
    files = sorted(glob.glob(str(args.calib_dir / "calibration*.jsonl")))
    for path in files:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                unit = rec.get("unit")
                if not unit:
                    continue
                prev = latest.get(unit)
                if prev is None or str(rec.get("finished_at")) > str(
                        prev.get("finished_at")):
                    latest[unit] = rec

    tol_map, status_counts, no_tol = {}, {}, []
    for unit, rec in sorted(latest.items()):
        status = rec.get("control_status")
        status_counts[status] = status_counts.get(status, 0) + 1
        tol = rec.get("calibrated_tol")
        if tol is None:
            no_tol.append(unit)
            continue
        tol_map[unit] = tol

    payload = {
        "source_files": files,
        "dedup_rule": "latest finished_at wins",
        "units_total": len(latest),
        "units_with_tol": len(tol_map),
        "units_without_tol": no_tol,
        "status_counts": status_counts,
        "map": tol_map,
    }
    args.out.write_text(json.dumps(payload, indent=1, sort_keys=True),
                        encoding="utf-8")
    print(json.dumps({k: payload[k] for k in
                      ("units_total", "units_with_tol", "status_counts")},
                     indent=2))
    print("written:", args.out)


if __name__ == "__main__":
    main()
