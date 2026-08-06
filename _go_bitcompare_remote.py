#!/usr/bin/env python3
"""Deployment gate: bit-exactness comparison OLD path vs NEW path.

Runs ON THE REMOTE HOST, CPU-only (CUDA_VISIBLE_DEVICES must be empty),
against the STAGED worker (env MK_STAGED_WORKER) and the production
policy bank in /root/mk_v2.  Touches no experiment state.

Compares, per (kernel, policy, seed=sub_index round order as in production):
  OLD:  _seed_all(seed); template = get_inputs(); policy(clone_tree(template), seed)
  NEW:  _seed_all(seed); template = <single cached>|get_inputs(); policy(template, seed)
and asserts torch.equal (bit-exact), identical dtype/shape/stride, plus
summary equality (new fast _tensor_summary vs legacy implementation).

Coverage: light kernel L1_P1 full size; heavy P53 and P96 at reduced scale
(all 21 policies x 3 seeds each); heavy P53 FULL 8.6GB tensor for 2 cheap
policies x 1 seed and full-size summary equality (memory-bounded).
"""
import importlib.util
import json
import os
import random
import sys

sys.path.insert(0, "/root/mk_v2")
import torch  # noqa: E402

assert not torch.cuda.is_available() or os.environ.get(
    "CUDA_VISIBLE_DEVICES") == "", "run CPU-only"

from src.stress.policy_bank import STRESS_POLICIES, get_all_policy_names  # noqa: E402
from src.validation import clone_tree  # noqa: E402

WORKER = os.environ.get("MK_STAGED_WORKER", "/tmp/_mk_stage/_mutant_worker.py")
spec = importlib.util.spec_from_file_location("_mw_staged", WORKER)
mw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mw)

BASE_SEED = 50000
EQUIV_RUNS = 40
REPEATS = 3
FAILURES = []
CHECKS = {"tensor_equal": 0, "summary_equal": 0}


def seed_all(seed):
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed % (2 ** 32))
    except ImportError:
        pass
    torch.manual_seed(seed)


def legacy_summary(t):
    if isinstance(t, torch.Tensor):
        mean = (float(t.mean().item())
                if t.numel() > 0 and t.is_floating_point() else None)
        return {
            "shape": list(t.shape), "dtype": str(t.dtype),
            "min": float(t.min()) if t.numel() > 0 else None,
            "max": float(t.max()) if t.numel() > 0 else None,
            "mean": mean,
            "has_nan": bool(t.isnan().any()) if t.is_floating_point() else False,
            "has_inf": bool(t.isinf().any()) if t.is_floating_point() else False,
        }
    return {"type": type(t).__name__, "value": str(t)[:100]}


def same_summary(a, b):
    if set(a) != set(b):
        return False
    for k in a:
        x, y = a[k], b[k]
        if isinstance(x, float) and x != x:
            if not (isinstance(y, float) and y != y):
                return False
        elif x != y:
            return False
    return True


def compare_tree(tag, old, new, check_summary=True):
    if type(old) is not type(new) or len(old) != len(new):
        FAILURES.append(f"{tag}: tree structure mismatch")
        return
    for i, (a, b) in enumerate(zip(old, new)):
        if isinstance(a, torch.Tensor):
            ok = (torch.equal(a, b) and a.dtype == b.dtype
                  and a.shape == b.shape and a.stride() == b.stride())
            CHECKS["tensor_equal"] += 1
            if not ok:
                FAILURES.append(f"{tag}[{i}]: tensor mismatch")
            elif check_summary:
                CHECKS["summary_equal"] += 1
                if not same_summary(legacy_summary(b), mw._tensor_summary(b)):
                    FAILURES.append(f"{tag}[{i}]: summary mismatch")
        elif a != b:
            FAILURES.append(f"{tag}[{i}]: non-tensor leaf mismatch")


def run_case(kernel_name, get_inputs, policies, seeds_slice=None):
    """Replay production round order for one kernel through both paths."""
    reps = range(REPEATS) if seeds_slice is None else seeds_slice
    # NEW path state (mirrors the staged worker's cache logic)
    stress_template = None
    reusable = False
    for policy_name in policies:
        policy_fn = STRESS_POLICIES[policy_name]
        for si in reps:
            seed = BASE_SEED + EQUIV_RUNS + si
            # OLD path
            seed_all(seed)
            template_old = get_inputs()
            out_old = policy_fn(clone_tree(template_old), seed)
            del template_old  # bound the transient peak for full-size cases
            # NEW path
            seed_all(seed)
            if reusable:
                template_new = stress_template
            else:
                template_new = get_inputs()
                if stress_template is None:
                    stress_template = template_new
                    reusable = mw._all_float_tensor_tree(template_new)
            out_new = policy_fn(template_new, seed)
            compare_tree(f"{kernel_name}/{policy_name}/s{si}", out_old, out_new)
            del out_old, out_new
    # cached template must be pristine (== fresh regen of its own seed)
    if stress_template is not None and reusable:
        seed_all(BASE_SEED + EQUIV_RUNS + (reps[0] if seeds_slice else 0))
        fresh = get_inputs()
        compare_tree(f"{kernel_name}/cache_pristine", fresh, stress_template,
                     check_summary=False)


def main():
    all_policies = get_all_policy_names()
    assert len(all_policies) == 21, all_policies

    # light kernel, FULL size (L1_P1: two 4096x4096 rand)
    run_case("P1_full",
             lambda: [torch.rand(4096, 4096), torch.rand(4096, 4096)],
             all_policies)

    # heavy P53 shape, reduced (128x512x511 ~ 33MB) - all policies x 3 seeds
    run_case("P53_scaled",
             lambda: [torch.rand(128, 512, 511)],
             all_policies)

    # heavy P96 structure, reduced (two tensors + scalar-scale product)
    def p96_scaled():
        scale = torch.rand(())
        return [torch.rand(2048, 2048) * scale, torch.rand(2048, 2048)]
    run_case("P96_scaled", p96_scaled, all_policies)

    # non-reusable guard exercise: template with an int tensor leaf must
    # take the regeneration path and still match the old path bit-for-bit
    def mixed_tree():
        return [torch.rand(256, 256), torch.arange(64)]
    run_case("mixed_guard", mixed_tree,
             ["boundary_last_element", "structured_ramp", "sparse"])

    # heavy P53 FULL size (8.6GB): two cheap policies x 1 seed
    run_case("P53_FULL",
             lambda: [torch.rand(128, 4096, 4095)],
             ["boundary_last_element", "extreme_magnitude"],
             seeds_slice=[0])

    # full-size summary equality on the raw 8.6GB template
    seed_all(BASE_SEED)
    big = torch.rand(128, 4096, 4095)
    CHECKS["summary_equal"] += 1
    if not same_summary(legacy_summary(big), mw._tensor_summary(big)):
        FAILURES.append("P53_FULL_template: summary mismatch")
    del big

    print(json.dumps({
        "checks": CHECKS,
        "failures": FAILURES,
        "verdict": "ALL_GREEN" if not FAILURES else "FAILED",
    }, indent=1))
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
