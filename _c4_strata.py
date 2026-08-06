"""Stratified proportional allocation for the C4 pre-registered subsample.

Arithmetic only over the frozen manifest: computes the per-stratum quotas for
n = 60 under two remainder rules and reports the realised inclusion
probabilities of each, so the pre-registration can state which rule it adopts
and what pi_i actually is.  This does NOT draw a sample.
"""
import hashlib
import io
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

MANIFEST = Path("external/C4_tritonbench/data/TritonBench_G_v1.json")
N_SAMPLE = 60


def load_strata():
    raw = MANIFEST.read_bytes()
    manifest = json.loads(raw.decode("utf-8"))
    counts = Counter(record.get("difficulty") for record in manifest)
    return raw, manifest, dict(sorted(counts.items()))


def largest_remainder(counts, n):
    total = sum(counts.values())
    exact = {k: Fraction(v * n, total) for k, v in counts.items()}
    quota = {k: int(v) for k, v in exact.items()}
    remainder = {k: exact[k] - quota[k] for k in counts}
    short = n - sum(quota.values())
    order = sorted(counts, key=lambda k: (-remainder[k], k))
    for key in order[:short]:
        quota[key] += 1
    return quota, exact, remainder, short


def main():
    raw, manifest, counts = load_strata()
    total = sum(counts.values())
    print("manifest: %s" % MANIFEST)
    print("  records: %d   sha256: %s" % (len(manifest),
                                          hashlib.sha256(raw).hexdigest()))
    print("  strata (difficulty): %s" % counts)
    print("  target sampling fraction n/N = %d/%d = %.6f"
          % (N_SAMPLE, total, N_SAMPLE / total))

    quota, exact, remainder, short = largest_remainder(counts, N_SAMPLE)
    print("\n=== rule A: proportional allocation, largest-remainder rounding ===")
    print("%-11s %7s %12s %8s %8s %10s %12s"
          % ("difficulty", "N_h", "exact quota", "floor", "remain", "quota n_h",
             "pi_i = n_h/N_h"))
    for key in sorted(counts):
        print("%-11s %7d %12.4f %8d %8.4f %10d %12.6f"
              % (key, counts[key], float(exact[key]), int(exact[key]),
                 float(remainder[key]), quota[key], quota[key] / counts[key]))
    print("%-11s %7d %12.4f %8s %8s %10d"
          % ("total", total, float(sum(exact.values())), "", "",
             sum(quota.values())))
    pis = [quota[k] / counts[k] for k in counts]
    print("  surplus seats distributed by largest remainder: %d" % short)
    print("  pi_i range: %.6f .. %.6f (target %.6f)"
          % (min(pis), max(pis), N_SAMPLE / total))
    print("  max deviation from the target: %+.1f%% / %+.1f%%"
          % (100 * (min(pis) / (N_SAMPLE / total) - 1),
             100 * (max(pis) / (N_SAMPLE / total) - 1)))
    print("  -> pi_i is NOT constant; the HT/Hajek weights must use these "
          "realised values, not n/N")

    print("\n=== rule B: floors fixed + surplus seats drawn by seeded "
          "systematic sampling with probabilities equal to the remainders ===")
    print("%-11s %7s %8s %10s %14s %14s"
          % ("difficulty", "N_h", "floor", "P(extra)", "E[n_h]", "pi_i"))
    floors = {k: int(exact[k]) for k in counts}
    for key in sorted(counts):
        p_extra = float(remainder[key])
        expected = floors[key] + p_extra
        print("%-11s %7d %8d %10.4f %14.4f %14.6f"
              % (key, counts[key], floors[key], p_extra, expected,
                 expected / counts[key]))
    print("%-11s %7d %8d %10.4f %14.4f"
          % ("total", total, sum(floors.values()),
             float(sum(remainder.values())),
             sum(floors.values()) + float(sum(remainder.values()))))
    print("  remainders sum to exactly %s = the %d surplus seats, so a "
          "systematic draw allocates exactly %d of them"
          % (sum(remainder.values()), short, short))
    print("  pi_i is exactly %.6f for every task; stratum sizes are the only "
          "random part, and the total stays exactly %d"
          % (N_SAMPLE / total, N_SAMPLE))

    print("\n=== rule C (reference only): collapse the two tiny strata ===")
    collapsed = {"low (difficulty 1-2)": counts.get("1", 0) + counts.get("2", 0),
                 "mid (difficulty 3)": counts.get("3", 0),
                 "high (difficulty 4-5)": counts.get("4", 0) + counts.get("5", 0)}
    q3, e3, r3, s3 = largest_remainder(collapsed, N_SAMPLE)
    for key in collapsed:
        print("  %-22s N_h=%3d quota=%3d pi_i=%.6f"
              % (key, collapsed[key], q3[key], q3[key] / collapsed[key]))
    pis3 = [q3[k] / collapsed[k] for k in collapsed]
    print("  surplus seats: %d ; pi_i range %.6f .. %.6f (target %.6f)"
          % (s3, min(pis3), max(pis3), N_SAMPLE / total))

    out = {
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "manifest_records": len(manifest),
        "n_sample": N_SAMPLE,
        "strata_sizes": counts,
        "rule_a_largest_remainder": {
            "quota": quota,
            "pi_i": {k: quota[k] / counts[k] for k in counts},
            "surplus_seats": short,
        },
        "rule_b_randomised_remainder": {
            "floors": floors,
            "p_extra": {k: float(remainder[k]) for k in counts},
            "pi_i": N_SAMPLE / total,
            "surplus_seats": short,
        },
    }
    Path("_c4_strata_quotas.json").write_text(
        json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print("\nwrote _c4_strata_quotas.json")


if __name__ == "__main__":
    main()
