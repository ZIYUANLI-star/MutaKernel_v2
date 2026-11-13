#!/usr/bin/env python3
"""Render Figure 1 of the evaluation section from the authoritative aggregation.

The curves are the ``supplement.fixed_horizon`` detection grids: for each
shared-oracle row, the number of subjects whose first in-scope failure has
occurred by a given cumulative parent wall-clock.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STYLE = {
    "M-ctx": ("B6 composite context arm", "#1b4965", "-", 2.2),
    "M-full": ("M-full", "#c1121f", "-", 1.8),
    "M-dir": ("M-dir", "#e07a5f", "--", 1.8),
    "B5": ("B5 boundary values", "#3d5a80", "-.", 1.3),
    "B4": ("B4 value-diversified", "#98c1d9", "-.", 1.3),
    "B3": ("B3 IID-32", "#6c757d", ":", 1.3),
    "B1u": ("B1u anchor (5 draws)", "#adb5bd", ":", 1.3),
}
ORDER = ("M-ctx", "M-full", "M-dir", "B5", "B4", "B3", "B1u")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--aggregate",
        type=Path,
        default=PROJECT_ROOT / "_final_outputs" / "fse_v4_authoritative.json",
    )
    parser.add_argument(
        "--out", type=Path, default=PROJECT_ROOT / "_final_outputs" / "fig1_detection_curves"
    )
    args = parser.parse_args()

    aggregate = json.loads(args.aggregate.read_text(encoding="utf-8"))
    horizon = aggregate["supplement"]["fixed_horizon"]

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    for name in ORDER:
        row = horizon[name]
        label, colour, dash, width = STYLE[name]
        ax.plot(
            row["curve_grid_s"],
            row["curve_detected"],
            label=label,
            color=colour,
            linestyle=dash,
            linewidth=width,
        )
    ax.set_xlabel("cumulative parent wall-clock per subject (s)")
    ax.set_ylabel("subjects with a strict witness")
    ax.set_xlim(0, 300)
    ax.set_ylim(0, 720)
    ax.grid(True, linewidth=0.4, alpha=0.4)
    ax.axvline(52.0, color="black", linewidth=0.7, alpha=0.5)
    ax.annotate(
        "compilation floor\n(first invocation)",
        xy=(52, 700),
        xytext=(66, 660),
        fontsize=7.5,
        arrowprops={"arrowstyle": "-", "linewidth": 0.6},
    )
    ax.legend(fontsize=7.5, loc="lower right", framealpha=0.95)
    fig.tight_layout()
    for suffix in (".pdf", ".png"):
        target = args.out.with_suffix(suffix)
        fig.savefig(target, dpi=200)
        print("wrote", target)


if __name__ == "__main__":
    main()
