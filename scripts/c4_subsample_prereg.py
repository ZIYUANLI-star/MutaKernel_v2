#!/usr/bin/env python3
"""C4 (TritonBench-G) preregistered equal-probability subsample, n=60.

Implements the protocol frozen in
`MutakernelV2/实验/补充实验数据/E3_契约缺口补齐计划_L3与C4.md` §2.3.2
(2026-07-30 拍板):

  * sampling frame: all 184 manifest records (never the 87 literal-shape ones);
  * n = 60, stratified by the manifest `difficulty` field (5 strata),
    proportional allocation, floor quotas, and the 3 remainder slots assigned
    by RULE B: one seeded systematic-sampling pass over the stratum
    remainders, so that every task's inclusion probability is EXACTLY 60/184;
  * within-stratum simple random sampling without replacement;
  * a seeded uniform permutation of the 60 selected tasks fixes the writing
    order (any prefix of length m is itself an equal-probability sample with
    pi = m/184);
  * seed = 42 for every random draw (protocol constant, same as E0/E1);
  * outputs the four reproducibility artifacts of §2.3.2(5) plus the
    Monte-Carlo self-check of §2.3.2(4).

Run:  python scripts/c4_subsample_prereg.py
Outputs (under MutakernelV2/实验/补充实验数据/contracts/):
  c4_subsample.preregistration.json   (protocol + evidence + ordered sample)
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "external/C4_tritonbench/data/TritonBench_G_v1.json"
OUT_DIR = ROOT / "MutakernelV2/实验/补充实验数据/contracts"
OUT = OUT_DIR / "c4_subsample.preregistration.json"

SEED = 42
N_TARGET = 60
EXPECTED_MANIFEST_SHA = (
    "78d730f062d6c6ee1c369da0df3bd98b7039c192313600b578ecda9a55d8b0a2")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def allocate_remainders(strata, rng):
    """RULE B: seeded systematic sampling over stratum remainders.

    The remainders sum exactly to the number of leftover slots R; a single
    uniform start u in [0,1) and points u, u+1, ..., u+R-1 on the cumulative
    remainder axis select exactly R strata, each with probability equal to
    its remainder.  Returns the set of difficulties given an extra slot.
    """
    remainders = [(d, s["remainder"]) for d, s in sorted(strata.items())]
    total = sum(r for _, r in remainders)
    n_slots = round(total)
    assert abs(total - n_slots) < 1e-9, "remainders must sum to an integer"
    u = rng.random()
    points = [u + i for i in range(n_slots)]
    chosen = []
    cum = 0.0
    idx = 0
    for d, r in remainders:
        lo, hi = cum, cum + r
        while idx < len(points) and lo <= points[idx] < hi:
            chosen.append(d)
            idx += 1
        cum = hi
    assert len(chosen) == n_slots
    assert len(set(chosen)) == len(chosen), \
        "a stratum with remainder < 1 can receive at most one extra slot"
    return set(chosen)


def draw_sample(records, seed):
    """One full allocation + within-stratum draw + writing permutation."""
    rng = random.Random(seed)
    n_total = len(records)
    strata = {}
    for i, rec in enumerate(records):
        d = int(rec["difficulty"])
        strata.setdefault(d, {"tasks": []})["tasks"].append(i)
    for d, s in strata.items():
        exact = len(s["tasks"]) * N_TARGET / n_total
        s["N_h"] = len(s["tasks"])
        s["exact_quota"] = exact
        s["floor"] = math.floor(exact)
        s["remainder"] = exact - math.floor(exact)

    extra = allocate_remainders(strata, rng)
    selected = []
    for d in sorted(strata):
        s = strata[d]
        n_h = s["floor"] + (1 if d in extra else 0)
        s["n_h"] = n_h
        picked = rng.sample(sorted(s["tasks"]), n_h)
        selected.extend(picked)
    assert len(selected) == N_TARGET

    order = list(selected)
    rng.shuffle(order)
    return strata, extra, selected, order


def main():
    raw = MANIFEST.read_bytes()
    manifest_sha = sha256_bytes(raw)
    assert manifest_sha == EXPECTED_MANIFEST_SHA, (
        "manifest drifted: %s" % manifest_sha)
    records = json.loads(raw.decode("utf-8"))
    assert len(records) == 184
    files = [r["file"] for r in records]
    assert len(set(files)) == 184, "task ids must be unique"

    strata, extra, selected, order = draw_sample(records, SEED)

    # pi_i is analytically 60/184 for every task under rule B; verify.
    target_pi = N_TARGET / len(records)
    for d, s in strata.items():
        pi = (s["floor"] + s["remainder"]) / s["N_h"]
        assert abs(pi - target_pi) < 1e-12, (d, pi, target_pi)

    # Monte-Carlo self-check of the allocation mechanism (mechanism only,
    # preregistration-time evidence; the real draw uses SEED above).
    mc_counts = Counter()
    reps = 1000
    for rep in range(reps):
        rng = random.Random((SEED, "mc", rep))
        chosen = allocate_remainders(strata, rng)
        for d in chosen:
            mc_counts[d] += 1
    mc = {str(d): {"empirical": mc_counts.get(d, 0) / reps,
                   "expected": round(strata[d]["remainder"], 6)}
          for d in sorted(strata)}

    ordered_sample = []
    for rank, i in enumerate(order, 1):
        rec = records[i]
        ordered_sample.append({
            "writing_order": rank,
            "task_id": rec["file"],
            "repo": rec.get("repo"),
            "difficulty": int(rec["difficulty"]),
            "star": rec.get("star"),
            "pi_i": target_pi,
        })

    payload = {
        "protocol": {
            "id": "c4-subsample-p2-random-v1",
            "basis": "E3_契约缺口补齐计划_L3与C4.md §2.3.2 (2026-07-30 拍板)",
            "frame": "all 184 TritonBench_G_v1 tasks",
            "n": N_TARGET,
            "stratification": "manifest difficulty (5 strata), proportional "
                              "allocation, floor quotas, remainder rule B "
                              "(seeded systematic sampling)",
            "stopping_rule": "write until n=60 references are authored; if "
                             "the person-hour budget is exhausted first, "
                             "stop then (prefix of length m is a valid "
                             "pi=m/184 sample); no other stopping allowed",
            "seed": SEED,
            "undecidable_tasks": "never resampled or replaced (§2.3.2(7))",
        },
        "evidence": {
            "manifest_sha256": manifest_sha,
            "script_sha256": sha256_bytes(
                Path(__file__).read_bytes()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "strata": {str(d): {
                "N_h": s["N_h"], "exact_quota": round(s["exact_quota"], 6),
                "floor": s["floor"], "remainder": round(s["remainder"], 6),
                "n_h": s["n_h"], "got_extra_slot": d in extra,
            } for d, s in sorted(strata.items())},
            "pi_constant_check": "max|pi_i - 60/184| < 1e-12 asserted",
            "monte_carlo_selfcheck": {
                "reps": reps, "per_stratum": mc,
                "note": "empirical extra-slot frequency vs remainder; "
                        "mechanism check only, real draw uses seed=42",
            },
        },
        "sample_by_writing_order": ordered_sample,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("strata:", {d: s["n_h"] for d, s in sorted(strata.items())},
          "extra slots ->", sorted(extra))
    print("MC self-check:", {k: v for k, v in mc.items()})
    print("first 10 by writing order:",
          [t["task_id"] for t in ordered_sample[:10]])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
