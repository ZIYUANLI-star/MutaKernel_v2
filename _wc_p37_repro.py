#!/usr/bin/env python3
"""Minimal, oracle-free reproduction of the L1_P37 grid-barrier race.

The candidate kernel (KernelBench level1/37_FrobeniusNorm_, CUDA variant used as
E1 subject ``L1_P37``) fuses the whole Frobenius normalisation into ONE launch:

    phase 1  each block reduces its slice into norm[blockIdx.x]
    phase 2  EVERY block's thread 0 does
                 for (i = 0; i < gridDim.x; i++) total_sum += norm[i];
             i.e. it reads the partial sums of *other* blocks
    phase 3  each block scales its slice by 1/sqrt(total_sum + 1e-8)

``__syncthreads()`` is a block-local barrier.  Nothing orders phase 1's writes
against phase 2's reads *across* blocks, and ``block_sums`` is zero-initialised,
so a block that runs early reads 0 for the blocks that have not finished and
computes a *smaller* total_sum -- hence a *larger* scale factor -- than a block
that runs late.

Two consequences, both checked here without any reference implementation and
without any tolerance:

  A. ONE forward pass can contain MORE THAN ONE distinct scale factor.
     output[i] / input[i] is exactly the inv_norm that the block owning i used,
     so counting distinct ratios inside a single output is a direct read-out of
     how many different values of ``final_norm`` the blocks computed.  >1 is a
     proof of the missing grid barrier that cannot be explained by rounding.

  B. Repeated forward passes on the SAME input give different outputs.

Both are run under uniform rand (the KernelBench get_inputs distribution, where
the effect is small enough to hide inside rtol=1e-2) and under the E1
``sparse_extreme`` stress distribution (99% zeros + 1% randn*1e4, where the norm
is dominated by a handful of huge values, so a single missed block moves the
result out of tolerance).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, "/root/mk_v2")
os.environ.setdefault("PATH", "/usr/local/cuda/bin:/root/miniconda3/bin:/usr/bin:/bin")

import torch  # noqa: E402

from src.stress.policy_bank import STRESS_POLICIES  # noqa: E402

OUT = "/root/mk_v2_runs/e1/witness_confirmation/p37_race_minimal_repro.json"
REPEATS = 8
# Full production geometry is 112x64x512x512 (7.5 GiB/tensor).  The race is a
# property of the launch configuration (num_blocks = min(ceil(n/1024), 1024)),
# so it reproduces at any size that saturates the 1024-block cap; both are run.
SHAPES = [(112, 64, 512, 512), (2048, 1024)]


def load_candidate():
    from pathlib import Path

    import scripts.run_e1_probe_study as ps
    from src.mutengine.mutant_runner import _load_module_from_source

    pfs = ps._load_probe_files(Path("/root/mk_v2_runs/e1"))
    for kf in pfs:
        kk = kf["kernel"]
        if (kk["level"], kk["problem_id"]) == (1, 37):
            mod = _load_module_from_source(
                kf["kernel_source"], "p37_race_repro", "/root/mk_v2_runs/torch_ext")
            return mod.ModelNew().cuda().eval(), kf["kernel_source"]
    raise SystemExit("L1_P37 not found in the probe files")


def scale_factors(x, y):
    """Distinct values of output/input, which equals the block's own inv_norm."""
    mask = x.abs() > 0
    ratio = (y[mask].double() / x[mask].double())
    uniq = torch.unique(ratio)
    return uniq


def make_input(shape, dist, seed):
    if dist == "uniform_rand":
        g = torch.Generator().manual_seed(seed)
        return torch.rand(*shape, generator=g).cuda()
    template = [torch.rand(*shape)]
    return STRESS_POLICIES[dist](template, seed)[0].cuda()


def main():
    model, source = load_candidate()
    assert "__syncthreads" in source and "gridDim.x" in source
    report = {
        "subject": "L1_P37 (KernelBench level1/37_FrobeniusNorm_, CUDA candidate)",
        "defect": "missing grid-level barrier between the per-block partial-sum "
                  "write (phase 1) and the cross-block partial-sum read "
                  "(phase 2) inside a single kernel launch",
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "device": torch.cuda.get_device_name(0),
        "repeats": REPEATS,
        "cases": [],
        "at": datetime.now().isoformat(),
    }
    for shape in SHAPES:
        for dist in ("uniform_rand", "sparse_extreme", "boundary_last_element"):
            try:
                x = make_input(shape, dist, 50040)
            except Exception as exc:
                report["cases"].append({"shape": list(shape), "dist": dist,
                                        "error": "%s: %s" % (type(exc).__name__, exc)})
                continue
            ref = torch.norm(x.double(), p="fro")
            outs, scales = [], []
            with torch.no_grad():
                for _ in range(REPEATS):
                    y = model(x)
                    torch.cuda.synchronize()
                    uniq = scale_factors(x, y)
                    scales.append(uniq)
                    outs.append(y.clone())
            n_distinct = [int(u.numel()) for u in scales]
            implied = [(1.0 / u).tolist()[:6] for u in scales]
            bitwise_same = [bool(torch.equal(outs[0], o)) for o in outs[1:]]
            maxdiff = [float((outs[0] - o).abs().max()) for o in outs[1:]]
            report["cases"].append({
                "shape": list(shape),
                "dist": dist,
                "reference_frobenius_norm_fp64": float(ref),
                "distinct_scale_factors_per_pass": n_distinct,
                "implied_norms_per_pass_first6": implied,
                "outputs_bitwise_identical_to_pass0": bitwise_same,
                "max_abs_diff_vs_pass0": maxdiff,
                "race_visible_within_one_pass": any(n > 1 for n in n_distinct),
                "race_visible_across_passes": not all(bitwise_same),
            })
            print(json.dumps(report["cases"][-1], indent=1), flush=True)
            del x, outs, scales
            torch.cuda.empty_cache()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print("WROTE", OUT)


if __name__ == "__main__":
    main()
