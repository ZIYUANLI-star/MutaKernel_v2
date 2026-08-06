#!/usr/bin/env python3
"""Feasibility microbenchmarks for input-generation optimisation candidates.

READ-ONLY wrt experiment state. GPU use capped at 0.15 memory fraction
(~12.3GB of 80GB; lanes currently use ~47GB, ~34GB free). Every GPU test
frees its tensors and empties the cache before the next. CPU peak < 10GB.
Runs ON THE REMOTE HOST; prints JSON.
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/root/mk_v2")
import torch  # noqa: E402

R = {}
P53 = (128, 4096, 4095)      # 2.147e9 elems, 8.0 GiB fp32
P91 = (32768, 32768)         # 1.074e9 elems, 4.0 GiB fp32
# GPU tests run at a 2 GiB probe size (0.5e9 elems) so the transient peak
# stays <=5 GiB with ~15 GiB free on the shared GPU; generation/transform
# ops are bandwidth-bound, so full-size numbers scale linearly (x4.29 for
# P53, x2 for P91).
PGPU = (16384, 32768)


def cpu_time(fn, n=2):
    best = None
    for _ in range(n):
        t0 = time.perf_counter()
        out = fn()
        dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
        del out
    return round(best, 3)


def gpu_time(fn, n=3):
    torch.cuda.synchronize()
    best = None
    for _ in range(n):
        t0 = time.perf_counter()
        out = fn()
        torch.cuda.synchronize()
        dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
        del out
        torch.cuda.empty_cache()
    return round(best, 4)


def main():
    # ---------- GPU side ----------
    assert torch.cuda.is_available()
    torch.cuda.set_per_process_memory_fraction(0.15, 0)
    free_b, total_b = torch.cuda.mem_get_info(0)
    R["gpu_free_gb_before"] = round(free_b / 2**30, 1)

    # 1) GPU generation at the 2 GiB probe size
    gen = torch.Generator(device="cuda")
    gen.manual_seed(50000)
    R["gpu_rand_2GiB_s"] = gpu_time(
        lambda: torch.rand(*PGPU, device="cuda", generator=gen), n=3)

    # 2) GPU policy-like transforms at the 2 GiB probe size (peak ~5 GiB)
    def gpu_mixed_extremes():
        v = torch.randn(*PGPU, device="cuda", generator=gen)
        mask = torch.rand(PGPU, device="cuda", generator=gen) > 0.5
        v[mask] *= 10000.0
        v[~mask] *= 0.0001
        return v
    R["gpu_policy_mixed_extremes_2GiB_s"] = gpu_time(gpu_mixed_extremes, n=2)
    R["gpu_policy_extreme_magnitude_2GiB_s"] = gpu_time(
        lambda: torch.randn(*PGPU, device="cuda", generator=gen) * 1e6, n=2)

    # 3) GPU summaries (5 reductions) on a 2 GiB tensor
    vals = torch.randn(*PGPU, device="cuda", generator=gen)

    def gpu_summaries():
        return (float(vals.min()), float(vals.max()), float(vals.mean()),
                bool(vals.isnan().any()), bool(vals.isinf().any()))
    R["gpu_summaries_2GiB_s"] = gpu_time(gpu_summaries, n=3)
    del vals
    torch.cuda.empty_cache()

    # 4) H2D transfer of a pageable 2 GiB CPU tensor (what _normalise_args does)
    cpu2 = torch.rand(*PGPU)
    R["h2d_pageable_2GiB_s"] = gpu_time(lambda: cpu2.to("cuda"), n=2)
    del cpu2
    torch.cuda.empty_cache()

    # 5) RNG stream evidence: same seed, CPU vs CUDA generator -> different
    torch.manual_seed(123)
    cpu_head = torch.rand(4).tolist()
    g2 = torch.Generator(device="cuda")
    g2.manual_seed(123)
    gpu_head = torch.rand(4, device="cuda", generator=g2).cpu().tolist()
    R["rng_cpu_head_seed123"] = [round(v, 6) for v in cpu_head]
    R["rng_gpu_head_seed123"] = [round(v, 6) for v in gpu_head]

    # 6) policy_bank fns take a *CPU* torch.Generator: show it cannot drive
    #    CUDA generation (the documented incompatibility, not a crash test)
    try:
        torch.randn(4, device="cuda", generator=torch.Generator())
        R["cpu_generator_on_cuda"] = "accepted (unexpected)"
    except RuntimeError as exc:
        R["cpu_generator_on_cuda"] = f"RuntimeError: {str(exc)[:90]}"

    # ---------- CPU side ----------
    # 7) does thread count change torch.rand speed / values?
    def rand_p91_seeded():
        torch.manual_seed(777)
        return torch.rand(*P91)
    torch.set_num_threads(1)
    R["cpu_rand_P91_1thread_s"] = cpu_time(rand_p91_seeded, n=1)
    torch.set_num_threads(56)
    R["cpu_rand_P91_56thread_s"] = cpu_time(rand_p91_seeded, n=1)
    a = rand_p91_seeded()
    torch.set_num_threads(1)
    b = rand_p91_seeded()
    R["cpu_rand_bitequal_across_threads"] = bool(torch.equal(a, b))
    del a, b
    torch.set_num_threads(56)

    # 8) chunked parallel generation (uniform_ per slice, own generator per
    #    chunk) -- speed only; values necessarily differ from single-stream
    def chunked(n_workers=8):
        out = torch.empty(P91[0] * P91[1])
        step = out.numel() // n_workers

        def fill(i):
            g = torch.Generator()
            g.manual_seed(777 * 1000 + i)
            lo = i * step
            hi = out.numel() if i == n_workers - 1 else lo + step
            out[lo:hi].uniform_(generator=g)
        with ThreadPoolExecutor(n_workers) as ex:
            list(ex.map(fill, range(n_workers)))
        return out
    R["cpu_rand_P91_chunked8_s"] = cpu_time(chunked, n=1)

    # 9) summaries alternatives on the big P53 tensor
    torch.manual_seed(50000)
    x = torch.rand(*P53)
    R["cpu_summaries5_P53_s"] = cpu_time(
        lambda: (float(x.min()), float(x.max()), float(x.mean()),
                 bool(x.isnan().any()), bool(x.isinf().any())), n=2)
    R["cpu_aminmax_mean_P53_s"] = cpu_time(
        lambda: (torch.aminmax(x), float(x.mean())), n=2)

    # 10) template-cache bit-equality sanity: same seed -> same tensor
    torch.manual_seed(50040)
    t1 = torch.rand(1024, 1024)
    torch.manual_seed(50040)
    t2 = torch.rand(1024, 1024)
    R["same_seed_regen_bitequal"] = bool(torch.equal(t1, t2))

    R["gpu_free_gb_after"] = round(torch.cuda.mem_get_info(0)[0] / 2**30, 1)
    json.dump(R, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
