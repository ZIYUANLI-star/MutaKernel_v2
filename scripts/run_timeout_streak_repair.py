#!/usr/bin/env python3
"""Execute the frozen timeout-streak repair campaign on one GPU node.

Preflight, smoke, and execution logic are reused verbatim from
``run_minimal_repair_campaign.py``; only the run-id prefix differs so the two
campaigns stay distinguishable in the ledgers.

Run this with ``--max-parallel 1``.  Most repair cases are expected to sit at
the 180 s parent timeout, and GPU contention must not be able to turn a case
that would otherwise complete into a further timeout — that would defeat the
purpose of the repair.  The per-case timeout stays at the frozen 180 s and the
mid-campaign timeout-streak guard is simply not passed to the runner.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_minimal_repair_campaign as base  # noqa: E402

OLD_PREFIX = "minimal-repair-20260826"
NEW_PREFIX = "timeout-streak-repair-20260827"

_base_runner_command = base.runner_command


def runner_command(**kwargs) -> list[str]:
    command = _base_runner_command(**kwargs)
    index = command.index("--run-id")
    command[index + 1] = command[index + 1].replace(OLD_PREFIX, NEW_PREFIX)
    if "--timeout-streak-limit" in command:
        raise RuntimeError("the repair must not pass a timeout-streak limit")
    return command


base.runner_command = runner_command


if __name__ == "__main__":
    base.main()
