#!/usr/bin/env python3
"""CPU-only microbenchmark of the per-round input pipeline (READ-ONLY wrt
experiment state; no GPU, no CUDA init). Mimics the worker's code paths.

Run remotely under nice; prints JSON.
"""
import json
import sys
import time

sys.path.insert(0, "/root/mk_v2")

import torch  # noqa: E402

RESULTS = {"torch_threads": torch.get_num_threads()}


def t(label, fn, n=2):
    best = None
    for _ in range(n):
        t0 = time.perf_counter()
        out = fn()
        dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
        del out
    RESULTS[label] = round(best, 3)


def main():
    from src.validation import clone_tree
    from src.stress.policy_bank import STRESS_POLICIES

    shapes = {
        "P53_128x4096x4095": (128, 4096, 4095),
        "P91_32768x32768": (32768, 32768),
        "P27_4096x393216": (4096, 393216),
        "P1_4096x4096_light": (4096, 4096),
    }
    for name, shape in shapes.items():
        torch.manual_seed(50000)
        t(f"rand_{name}", lambda s=shape: torch.rand(*s), n=2)

    # deep-dive on the P53 shape
    torch.manual_seed(50000)
    x = torch.rand(128, 4096, 4095)
    template = [x]
    t("clone_tree_P53", lambda: clone_tree(template), n=2)
    for pol in ("extreme_magnitude", "sparse", "alternating_sign",
                "boundary_last_element", "structured_ramp"):
        fn = STRESS_POLICIES[pol]
        # full stress-generation path as in the worker:
        # policy_fn(clone_tree(template), seed) with the inner clone too
        t(f"policy_full_{pol}_P53",
          lambda f=fn: f(clone_tree(template), 50043), n=1)

    def summaries():
        return (float(x.min()), float(x.max()), float(x.mean()),
                bool(x.isnan().any()), bool(x.isinf().any()))
    t("summaries_P53", summaries, n=2)

    json.dump(RESULTS, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
