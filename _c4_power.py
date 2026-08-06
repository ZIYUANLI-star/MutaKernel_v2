"""Sample-size / precision trade-off for the C4 pre-registered random subsample.

Read-only arithmetic, no remote access.  Produces the n-options table that the
plan document quotes: for each candidate n, the expected confirmed-defect pool
under three prior prevalences, the Wilson 95% CI half-width for a coverage
estimate on that pool (with the finite-population correction and a task-level
design effect), the exact-McNemar discordant-pair count, and the person-hours.
Every input marked PRIOR is an assumption, not a measurement.
"""
import json
import math
from pathlib import Path

N_CORPUS = 184

# PRIOR: fraction of C4 tasks that carry at least one confirmed in-contract
# defect.  0.139 = E1's witnessed-non-equivalence rate among baseline survivors
# (73/527); 0.10 and 0.30 bracket it.  RQ1's own C2/C3/C5 prevalence will
# replace this the moment the audit closes.
PREVALENCES = (0.10, 0.139, 0.30)
# PRIOR: confirmed defects per defective task, and the intra-task correlation of
# "detected by a given validator" used for the design effect.
DEFECTS_PER_DEFECTIVE_TASK = 1.4
INTRA_TASK_RHO = 0.5
# PRIOR: coverage level at which the CI half-width is evaluated (widest near
# 0.5; 0.70 is the level the aggregate table is expected to sit at).
COVERAGE_AT = 0.70
# PRIOR: paired detection split used for the exact McNemar illustration
P10, P01 = 0.32, 0.02
# PRIOR: authoring and review cost per task
AUTHOR_MIN_H, AUTHOR_MAX_H = 20 / 60.0, 40 / 60.0
REVIEW_H_PER_TASK = 2 * 5 / 60.0
Z = 1.959964


def wilson(k, m):
    """Wilson score interval for k/m; returns (low, high)."""
    if m <= 0:
        return (0.0, 1.0)
    p = k / m
    d = 1 + Z * Z / m
    centre = (p + Z * Z / (2 * m)) / d
    spread = Z * math.sqrt(p * (1 - p) / m + Z * Z / (4 * m * m)) / d
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def row(n):
    fpc = math.sqrt(max(0.0, 1 - n / N_CORPUS))
    design_effect = 1 + (DEFECTS_PER_DEFECTIVE_TASK - 1) * INTRA_TASK_RHO
    out = {"n": n, "fpc": round(fpc, 3),
           "design_effect": round(design_effect, 3),
           "author_h": (round(n * AUTHOR_MIN_H, 1), round(n * AUTHOR_MAX_H, 1)),
           "review_h": round(n * REVIEW_H_PER_TASK, 1),
           "b9_units": 2 * n, "by_prevalence": {}}
    for q in PREVALENCES:
        defective = n * q
        pool = defective * DEFECTS_PER_DEFECTIVE_TASK
        effective = pool / design_effect
        k = COVERAGE_AT * effective
        low, high = wilson(k, effective)
        half = (high - low) / 2 * fpc
        discordant = pool * (P10 + P01)
        out["by_prevalence"]["%.3f" % q] = {
            "defective_tasks": round(defective, 1),
            "defect_pool": round(pool, 1),
            "effective_pool": round(effective, 1),
            "ci_half_width_points": round(100 * half, 1),
            "discordant_pairs": round(discordant, 1),
            "mcnemar_powered": discordant >= 8,
        }
    return out


def pool_for_half_width(target_points, q):
    """Smallest n whose CI half-width at COVERAGE_AT meets the target."""
    for n in range(10, N_CORPUS + 1):
        r = row(n)["by_prevalence"]["%.3f" % q]
        if r["ci_half_width_points"] <= target_points:
            return n, r
    return None, None


def main():
    ns = (30, 40, 50, 60, 80, 100, 120, 184)
    rows = [row(n) for n in ns]

    print("=== C4 pre-registered uniform random subsample: n options ===")
    print("corpus N = %d ; sampling frame = all %d tasks (NOT the 87 with "
          "literal shapes)" % (N_CORPUS, N_CORPUS))
    print("PRIOR prevalence q of tasks carrying >=1 confirmed defect: %s"
          % ", ".join("%.3f" % q for q in PREVALENCES))
    print("PRIOR defects per defective task %.1f ; intra-task rho %.1f "
          "-> design effect %.2f"
          % (DEFECTS_PER_DEFECTIVE_TASK, INTRA_TASK_RHO,
             1 + (DEFECTS_PER_DEFECTIVE_TASK - 1) * INTRA_TASK_RHO))
    print("CI evaluated at coverage %.2f ; Wilson 95%% x FPC sqrt(1-n/N)"
          % COVERAGE_AT)
    print()
    header = ("%-5s %-6s %-9s %-11s %-11s %-11s %-13s %-9s %s"
              % ("n", "FPC", "author h", "pool q=.10", "pool q=.139",
                 "pool q=.30", "CI+- q=.139", "review h", "B9 units"))
    print(header)
    print("-" * len(header))
    for r in rows:
        b = r["by_prevalence"]
        print("%-5d %-6.3f %-9s %-11.1f %-11.1f %-11.1f %-13s %-9.1f %d"
              % (r["n"], r["fpc"],
                 "%.0f-%.0f" % (r["author_h"][0], r["author_h"][1]),
                 b["0.100"]["defect_pool"], b["0.139"]["defect_pool"],
                 b["0.300"]["defect_pool"],
                 "%.0f pts" % b["0.139"]["ci_half_width_points"],
                 r["review_h"], r["b9_units"]))

    print()
    print("=== CI half-width by n and prevalence (percentage points) ===")
    print("%-5s %-12s %-12s %-12s" % ("n", "q=0.10", "q=0.139", "q=0.30"))
    for r in rows:
        b = r["by_prevalence"]
        print("%-5d %-12.0f %-12.0f %-12.0f"
              % (r["n"], b["0.100"]["ci_half_width_points"],
                 b["0.139"]["ci_half_width_points"],
                 b["0.300"]["ci_half_width_points"]))

    print()
    print("=== exact-McNemar discordant pairs (per-corpus significance) ===")
    print("assumed paired split p10=%.2f p01=%.2f; >=8 discordant pairs is the "
          "rough floor for 80%% power at alpha=0.05" % (P10, P01))
    print("%-5s %-14s %-14s %-14s" % ("n", "q=0.10", "q=0.139", "q=0.30"))
    for r in rows:
        b = r["by_prevalence"]
        print("%-5d %-14s %-14s %-14s"
              % (r["n"],
                 "%.1f %s" % (b["0.100"]["discordant_pairs"],
                              "ok" if b["0.100"]["mcnemar_powered"] else "under"),
                 "%.1f %s" % (b["0.139"]["discordant_pairs"],
                              "ok" if b["0.139"]["mcnemar_powered"] else "under"),
                 "%.1f %s" % (b["0.300"]["discordant_pairs"],
                              "ok" if b["0.300"]["mcnemar_powered"] else "under")))

    print()
    print("=== inverse: smallest n for a target CI half-width (q=0.139) ===")
    for target in (35, 30, 25, 20, 15):
        n, r = pool_for_half_width(target, 0.139)
        if n is None:
            print("   +-%2d pts : unreachable within the 184-task corpus" % target)
        else:
            print("   +-%2d pts : n=%3d (pool %.1f, author %.0f-%.0f h, "
                  "review %.1f h)"
                  % (target, n, r["defect_pool"], n * AUTHOR_MIN_H,
                     n * AUTHOR_MAX_H, n * REVIEW_H_PER_TASK))

    Path("_c4_power_options.json").write_text(
        json.dumps({"corpus_n": N_CORPUS, "priors": {
            "prevalences": list(PREVALENCES),
            "defects_per_defective_task": DEFECTS_PER_DEFECTIVE_TASK,
            "intra_task_rho": INTRA_TASK_RHO,
            "coverage_at": COVERAGE_AT, "p10": P10, "p01": P01},
            "rows": rows}, indent=2, sort_keys=True), encoding="utf-8")
    print("\nwrote _c4_power_options.json")


if __name__ == "__main__":
    main()
